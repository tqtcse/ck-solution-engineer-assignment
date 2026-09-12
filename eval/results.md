# Kết quả eval — v1 so với v2

Golden set: **12 câu**, chạy trên cùng một đoạn code retrieval, chỉ khác index.
Model: `claude-haiku-4-5`, `temperature=0`, `k=3`. Đo ngày 12/09/2026.

## Cách đo

| Chỉ số | Cách tính |
|---|---|
| `hit@3` | Trang chứa đáp án có nằm trong top-3 chunk không |
| `correct` | **Mọi** chuỗi trong `expected_answer_contains` xuất hiện trong câu trả lời |
| `grounded` | Câu trả lời có trích đúng `(page N)` |
| `top1_score` | Điểm cosine của chunk hạng 1 |

`correct` dùng **khớp chuỗi tất định**, không dùng LLM-judge. Với `"280,522"` thì `in`
là thước đo tốt hơn và rẻ hơn một model: nó không bao giờ rộng lượng với câu trả lời
gần đúng. LLM-judge chỉ dùng cho hai câu `out_of_scope`, nơi phải phán đoán
"đây có phải là từ chối không" — thứ không khớp chuỗi được.

Quyết định đó đã tự chứng minh giá trị: bản v2 đầu tiên tách bảng và phần diễn giải
thành hai chunk, chunk diễn giải lên hạng 1 nhưng nó viết *"$280.5 billion"* —
**làm tròn**. Khớp chuỗi bắt được ngay; LLM-judge sẽ chấm là đúng và lỗi này không
bao giờ lộ ra.

## Summary by question group

| Group | n | hit@3 v1 | hit@3 v2 | correct v1 | correct v2 | grounded v1 | grounded v2 |
|---|---|---|---|---|---|---|---|
| prose | 5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| table | 5 | 5/5 | 5/5 | 3/5 | 5/5 | 5/5 | 5/5 |
| out of scope | 2 | - | - | 2/2 | 2/2 | - | - |

## Per question

| id | type | top1 v1 | top1 v2 | correct v1 | correct v2 | pages v1 | pages v2 |
|---|---|---|---|---|---|---|---|
| q01 | fact | 0.227 | 0.211 | PASS | PASS | [3, 12] | [3, 12] |
| q02 | list | 0.556 | 0.539 | PASS | PASS | [3, 16] | [3, 16] |
| q03 | table_number | 0.335 | 0.476 | PASS | PASS | [3, 18] | [3, 4, 18] |
| q04 | table_number | 0.530 | 0.503 | PASS | PASS | [16, 18] | [16, 18] |
| q05 | table_multi | 0.316 | 0.266 | PASS | PASS | [18] | [13, 18] |
| q06 | person | 0.516 | 0.512 | PASS | PASS | [5] | [5] |
| q07 | risk | 0.595 | 0.564 | PASS | PASS | [13, 14] | [9, 14] |
| q08 | out_of_scope | 0.261 | 0.302 | PASS | PASS | [3, 4, 18] | [3, 4, 18] |
| q09 | out_of_scope | 0.150 | 0.158 | PASS | PASS | [5, 9, 18] | [5, 6, 18] |
| q10 | fact | 0.426 | 0.407 | PASS | PASS | [3, 12, 17] | [3, 12, 17] |
| q11 | table_number | 0.349 | 0.441 | FAIL | PASS | [3, 18] | [3, 5, 18] |
| q12 | table_number | 0.291 | 0.471 | FAIL | PASS | [18] | [18] |

## Score separation (basis for the retrieval threshold)

- **v1** in scope `0.227..0.595`, out of scope `0.150..0.261`, gap `-0.034` -> OVERLAP, no threshold separates them
- **v2** in scope `0.211..0.564`, out of scope `0.158..0.302`, gap `-0.091` -> OVERLAP, no threshold separates them

## Ba điều phải nói khi đọc bảng này

**1. Nhóm văn xuôi không đổi, nhóm bảng đi từ 3/5 lên 5/5.** Đó đúng là điều được
thiết kế để xảy ra: v2 chỉ thêm hiểu biết về **cấu trúc** tài liệu, nên nó chỉ cải
thiện những câu hỏi mà lời giải nằm trong cấu trúc. Nếu v2 cải thiện đều mọi nhóm
thì mới đáng ngờ — nghĩa là baseline đã bị làm cho tệ đi.

**2. Điểm số tụt nhưng chất lượng tăng.** Mọi câu văn xuôi đều giảm 0,02–0,05 ở v2,
vì tiền tố metadata `[page 18 | Item 6 | financial table]` chiếm chỗ trong embedding.
Thứ hạng thì không đổi. Đây là lý do **không** dùng ngưỡng cosine tuyệt đối làm cơ
chế từ chối: v2 retrieval tốt hơn nhưng điểm thấp hơn.

**3. Không tồn tại ngưỡng tách được hai nhóm.** Khe giữa điểm thấp nhất của câu
trong phạm vi và điểm cao nhất của câu ngoài phạm vi là **âm** ở cả hai phiên bản.
Vì vậy ngưỡng trong `_search_kb` giữ ở 0,3 và chỉ đóng vai trò tín hiệu ghi log;
việc từ chối do model quyết dựa trên đoạn trích, ràng buộc bằng system prompt.

## Chỗ v1 hỏng, cụ thể

**Lỗi 1 — bộ lọc nhiễu xoá mất số liệu tài chính thật.**
`extract.py` của v1 dùng `NOISE = ^\s*(Table of Contents|\d{1,3}|_{3,})\s*$` để bỏ
số trang. Nhưng nó bỏ **mọi** dòng chỉ có 1–3 chữ số — kể cả `596` (net income 2015)
và `467`–`504` (số cổ phiếu bình quân). Kiểm chứng trực tiếp trên index:

```
v1: '596' có trong index: False      v2: True
v1: '493' có trong index: False      v2: True
```

Đây không phải retrieval kém — **dữ liệu không tồn tại trong index**. Câu trả lời
của v1 cho q12 mô tả đúng triệu chứng: *"the actual numerical values for the diluted
shares are not included in the excerpts provided."* Không prompt nào cứu được.

**Lỗi 2 — bảng bị duỗi, số tách khỏi năm.**
`page.get_text()` trả về dòng năm một lần ở trên, rồi mỗi chỉ tiêu một hàng:

```
2015 / 2016 / 2017 (1) / 2018 / 2019
Net sales
$ 107,006  $ 135,987  $ 177,866  $ 232,887  $ 280,522
```

Nên trong index v1, `280,522` **không dính với 2019**. v2 ghép lại:

```
Statements of Operations - Net sales: 2015 107,006; ...; 2019 280,522
```

**`page.find_tables()` không dùng được trên file này.** Nó trả về 8 "bảng" ở trang 18
nhưng mỗi cái là một hàng đơn lẻ với tiêu đề `Col2..Col11`, và hàng chứa `280,522`
không nằm trong số đó. Đã bỏ, thay bằng bộ ghép năm viết tay.

## Một thay đổi làm sai lệch phép đo — và cách xử lý

Golden set ban đầu dùng tên riêng *"Amazon"*. Hai câu `out_of_scope` vì thế **đúng vì
lý do sai**: agent từ chối vì thấy tên công ty lạ (system prompt ẩn danh công ty),
chứ không phải vì năm tài chính nằm ngoài tài liệu. Đã đổi hết sang *"the company"*.

Nhưng việc đó **cũng vô tình sửa luôn q03 cho v1**. Đo trực tiếp:

| Câu hỏi gửi vào v1 | top1 | Trang top-3 | Có `280,522` |
|---|---|---|---|
| `What was Amazon net sales in 2019?` | 0,318 | 2, 3 | ❌ |
| `What were the company net sales in 2019?` | 0,316 | 3, 4, 18 | ✅ |

Chữ *"Amazon"* kéo trang 2 — **trang mục lục**, mở đầu bằng `AMAZON.COM, INC. FORM
10-K` — lên hạng 1. Bỏ tên riêng đi thì trang đó hết cạnh tranh và v1 tự lấy đúng
trang 18.

Bài học, và là lý do phải ghi lại: **một phần đáng kể của "v1 hỏng" ban đầu là do
cách đặt câu hỏi, không phải do preprocessing.** Nếu cứ giữ golden set cũ thì bảng
so sánh sẽ đẹp hơn nhưng sai. Sau khi chuẩn hoá câu hỏi, khác biệt còn lại giữa v1
và v2 **nhỏ hơn nhưng là thật**, và nằm đúng ở chỗ đo được: dữ liệu bị mất (q11, q12).

## Hai câu q11, q12 được thêm vào sau — nói rõ vì sao

10 câu ban đầu không phân biệt được v1 với v2 (cả hai 10/10). Sau khi phát hiện lỗi 1
bằng cách kiểm trực tiếp nội dung index, tôi thêm hai câu nhắm đúng vào khiếm khuyết
đó — tương đương viết **regression test cho một bug vừa tìm ra**:

- `q11` net income 2015 → `596`
- `q12` số cổ phiếu diluted 2017 → `493`

Đây là phần mở rộng **sau khi đã thấy kết quả**, nên không dùng nó để tuyên bố v2
"thắng" ở nghĩa thống kê. Nó chứng minh một điều hẹp hơn và chắc chắn hơn: có một
lớp câu hỏi mà v1 **không thể** trả lời vì dữ liệu đã bị xoá khỏi index, còn v2 thì
trả lời được.

## Còn lại gì chưa giải quyết

- **Golden set 12 câu** — khoảng tin cậy rộng, một câu đổi là 8%.
- **`hit@3` đo theo trang, không theo chunk**, vì golden set chỉ ghi `expected_page`.
  Phép đo này dễ dãi hơn thực tế: một trang có nhiều chunk.
- **Bảng trang 16** (diện tích mặt bằng) không có dòng năm nên bộ ghép không áp
  dụng được; nó vẫn nằm ở dạng văn xuôi. q04 vốn đã đạt nên chưa đáng làm thêm.
- **Tiền tố metadata là bản rẻ của contextual retrieval** — dựng từ metadata thay vì
  gọi LLM sinh câu ngữ cảnh cho từng chunk. Đổi một phần chất lượng lấy chi phí
  build bằng 0.
- **Chưa đo lại ngưỡng sau v2** một cách hệ thống; khe vẫn âm nên kết luận không đổi.
