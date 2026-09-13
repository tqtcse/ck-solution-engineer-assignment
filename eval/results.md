# Kết quả eval — v1 so với v2

Golden set: **38 câu**, chạy trên cùng một đoạn code retrieval, chỉ khác index.
Model: `claude-haiku-4-5`, `temperature=0`, `k=3`. Đo ngày 13/09/2026.

Bộ này đo **tầng retrieval + sinh câu trả lời**. Nó không chạy agent — phần đó ở
[results_agent.md](results_agent.md).

## Cách đo

| Chỉ số | Cách tính |
|---|---|
| `hit@3` | Trang chứa đáp án có nằm trong top-3 chunk không |
| `evidence` | Chuỗi đáp án có **thật sự nằm trong văn bản lấy về** không |
| `correct` | **Mọi** chuỗi trong `expected_answer_contains` xuất hiện trong câu trả lời |
| `grounded` | Câu trả lời có trích đúng `(page N)` |
| `top1_score` | Điểm cosine của chunk hạng 1 |

`evidence` thay thế vai trò của `hit@3`. `hit@3` đo **theo trang**, mà một trang có nhiều
chunk — nó báo đạt cho cả những câu mà con số đã bị xoá khỏi index, chỉ vì chunk khác cùng
trang lọt top-3. `evidence` nối top-3 chunk lại rồi tìm chuỗi đáp án trong đó, nên nó trả
lời đúng câu hỏi cần hỏi: **model có được đưa cho bằng chứng không.**

`correct` dùng **khớp chuỗi tất định**, không dùng LLM-judge. Với `"280,522"` thì `in` là
thước đo tốt hơn *và* rẻ hơn một model: nó không bao giờ rộng lượng với câu trả lời gần
đúng. LLM-judge chỉ dùng cho 6 câu `out_of_scope`, nơi phải phán đoán "đây có phải là từ
chối không" — thứ không khớp chuỗi được.

## Golden set được xây thế nào

38 câu: **17 văn xuôi**, **15 bảng**, **6 ngoài phạm vi**.

26 câu (q13–q38) viết **sau khi đọc tài liệu, trước khi chạy lần nào** — cố ý, để tránh
đúng cái bẫy của q11/q12 (xem mục cuối). Mỗi `expected_answer_contains` được kiểm tự động
là có thật trên đúng `expected_page`: **38/38 đạt, 0 ground truth sai.**

## Summary by question group

| Group | n | hit@3 v1 | hit@3 v2 | evidence v1 | evidence v2 | correct v1 | correct v2 | grounded v1 | grounded v2 |
|---|---|---|---|---|---|---|---|---|---|
| prose | 17 | 17/17 | 17/17 | 17/17 | 17/17 | 17/17 | 17/17 | 17/17 | 17/17 |
| table | 15 | 15/15 | 15/15 | **11/15** | **15/15** | **11/15** | **15/15** | 14/15 | 15/15 |
| out of scope | 6 | - | - | - | - | 6/6 | 6/6 | - | - |

```
v1  correct 34/38 = 89.5%   Wilson 95% CI [75.9%, 95.8%]
v2  correct 38/38 = 100%    Wilson 95% CI [90.8%, 100%]
```

## Ba điều phải nói khi đọc bảng này

**1. `hit@3` là 15/15 ở cả hai bản, `evidence` là 11/15 với 15/15.** Đây chính là lý do
`hit@3` bị thay. Với q11, q12, q31, q33, v1 lấy **đúng trang 18** nhưng con số cần tìm
không có trong chunk nào lấy về. Đo theo trang thì v1 hoàn hảo; đo theo nội dung thì v1
hỏng 4 câu.

**2. `evidence` trùng khít `correct` — 11/15 với 11/15, 15/15 với 15/15.** Không câu nào
model được đưa bằng chứng mà trả lời sai, cũng không câu nào trả lời đúng mà không có
bằng chứng. **Toàn bộ chênh lệch v1/v2 là chênh lệch dữ liệu, không phải chênh lệch khả
năng sinh văn bản.** Nếu xuất hiện câu `evidence=True, correct=False` thì đó mới là lỗi
prompt — không có câu nào như vậy.

**3. Nhóm văn xuôi 17/17 ở cả hai bản, không đổi.** Đó đúng là điều được thiết kế để xảy
ra: v2 chỉ thêm hiểu biết về **cấu trúc** tài liệu, nên nó chỉ cải thiện những câu mà lời
giải nằm trong cấu trúc. Nếu v2 cải thiện đều mọi nhóm thì mới đáng ngờ — nghĩa là
baseline đã bị làm cho tệ đi.

## Chỗ v1 hỏng, cụ thể — hai lỗi khác nhau

Bốn câu v1 trượt là `q11`, `q12`, `q31`, `q33`. Chúng chia làm hai nhóm nguyên nhân khác
hẳn nhau, và cả hai đều kiểm chứng được trực tiếp trên index.

**Lỗi 1 — bộ lọc nhiễu xoá mất số liệu thật.**
`extract.py` của v1 dùng `NOISE` khớp mọi dòng chỉ có 1–3 chữ số, để bỏ số trang. Nhưng
nó bỏ luôn cả số liệu:

```
'596' có trong index v1: False      v2: True     <- q11, net income 2015
'493' có trong index v1: False      v2: True     <- q12, diluted shares 2017
'467' có trong index v1: False      v2: True     <- q33, basic shares 2015
```

Đây không phải retrieval kém — **dữ liệu không tồn tại trong index**. Không prompt nào
cứu được.

**Lỗi 2 — bảng bị duỗi, số tách khỏi năm.**
`45,718` (q31, nợ dài hạn 2017) thì **có** trong index v1. Nhưng nó nằm thế này:

```
2015 2016 2017 2018 2019
(in millions)
Balance Sheets:
Total assets                 $ 64,747 $ 83,402 $ 131,310 $ 162,648 $ 225,248
Total long-term obligations  $ 17,477 $ 20,301 $  45,718 $  50,708 $  75,376
```

Dòng năm cách dòng giá trị 6 dòng, và mỗi chỉ tiêu có 5 số. Model không có cách nào biết
`45,718` thuộc 2017. v2 ghép lại từng cặp:

```
Balance Sheets - Total long-term obligations: 2015 17,477; ...; 2017 45,718; ...
```

**`page.find_tables()` không dùng được trên file này.** Nó trả về 8 "bảng" ở trang 18
nhưng mỗi cái là một hàng đơn lẻ với tiêu đề `Col2..Col11`, và hàng chứa `280,522` không
nằm trong số đó. Đã bỏ, thay bằng bộ ghép năm viết tay `_split_table_rows()`.

## Không tồn tại ngưỡng cosine tách được trong/ngoài phạm vi

```
v1  trong phạm vi 0.183..0.766   ngoài phạm vi 0.148..0.484   khe -0.301
v2  trong phạm vi 0.207..0.781   ngoài phạm vi 0.150..0.497   khe -0.290
```

Khe **âm sâu** ở cả hai bản. Câu ngoài phạm vi có điểm cao nhất là **q35** — *"What was
AWS segment revenue in 2019?"* — `0.484`, cao hơn 11 câu trong phạm vi. Nó nghe rất đúng
chủ đề, và tài liệu có nói nhiều về AWS; chỉ là **con số doanh thu theo segment nằm ở
Item 8 Note 10, không có trong bản trích 18 trang**. Không ngưỡng nào phân biệt được nó
với một câu hỏi thật.

Vì vậy ngưỡng `0.3` trong `_search_kb` giữ nguyên nhưng **chỉ đóng vai trò tín hiệu ghi
log**; việc từ chối do model quyết dựa trên đoạn trích, ràng buộc bằng system prompt. Và
nó hoạt động: **6/6 câu ngoài phạm vi bị từ chối đúng ở cả hai bản.**

## Chênh lệch v1/v2 có ý nghĩa thống kê chưa? Chưa.

```
McNemar: 4 cặp bất đồng, cả 4 cùng chiều (v2 đúng, v1 sai)
exact two-sided p = 0.125   -> KHÔNG đạt mức 0.05
```

Cần 5 cặp cùng chiều mới xuống `p = 0.0625`, 6 cặp mới xuống `0.031`. Hiện có 4.

Và phải nói thêm: **2 trong 4 cặp đó (`q11`, `q12`) được viết sau khi đã thấy v1 hỏng.**
Chỉ tính 2 câu viết mù (`q31`, `q33`) thì `p = 0.5`.

Nên **không tuyên bố "v2 thắng" theo nghĩa thống kê.** Thứ tuyên bố được thì chặt hơn và
chắc hơn nhiều: `evidence` cho thấy có một lớp câu hỏi mà v1 **không thể** trả lời, vì dữ
liệu đã bị xoá khỏi index hoặc bị tách khỏi năm của nó. Đó là **chứng minh tồn tại** —
chỉ cần n = 1, không cần p-value.

## Một thay đổi làm sai lệch phép đo — và cách xử lý

Golden set ban đầu dùng tên riêng *"Amazon"*. Hai câu `out_of_scope` vì thế **đúng vì lý
do sai**: agent từ chối vì thấy tên công ty lạ (system prompt ẩn danh công ty), chứ không
phải vì năm tài chính nằm ngoài tài liệu. Đã đổi hết sang *"the company"*.

Nhưng việc đó **cũng vô tình sửa luôn q03 cho v1**. Đo trực tiếp:

| Câu hỏi gửi vào v1 | top1 | Trang top-3 | Có `280,522` |
|---|---|---|---|
| `What was Amazon net sales in 2019?` | 0,318 | 2, 3 | ❌ |
| `What were the company net sales in 2019?` | 0,316 | 3, 4, 18 | ✅ |

Chữ *"Amazon"* kéo trang 2 — **trang mục lục**, mở đầu bằng `AMAZON.COM, INC. FORM 10-K`
— lên hạng 1. Bỏ tên riêng đi thì trang đó hết cạnh tranh và v1 tự lấy đúng trang 18.

Bài học, và là lý do phải ghi lại: **một phần đáng kể của "v1 hỏng" ban đầu là do cách
đặt câu hỏi, không phải do preprocessing.** Nếu cứ giữ golden set cũ thì bảng so sánh sẽ
đẹp hơn nhưng sai.

## q11, q12 được thêm vào sau — nói rõ vì sao

10 câu ban đầu không phân biệt được v1 với v2 (cả hai 10/10). Sau khi phát hiện lỗi 1
bằng cách kiểm trực tiếp nội dung index, tôi thêm hai câu nhắm đúng vào khiếm khuyết đó —
tương đương viết **regression test cho một bug vừa tìm ra**.

Đó là lý do 26 câu tiếp theo (q13–q38) được viết theo quy trình ngược lại: đọc hết 18
trang, viết câu hỏi phủ đều tài liệu, kiểm ground truth tự động, **rồi mới chạy**. `q31`
và `q33` rơi vào nhóm v1 trượt một cách tự nhiên — và mỗi câu lại chạm đúng một trong hai
lỗi preprocessing. Đó là bằng chứng mạnh hơn q11/q12 rất nhiều.

## Còn lại gì chưa giải quyết

- **`grounded` v1 = 14/15 ở nhóm bảng nhưng `correct` chỉ 11/15** — tức có câu v1 trích
  đúng số trang mà vẫn trả lời sai số. Trích dẫn đúng không bảo đảm nội dung đúng.
- **Bảng trang 16** (diện tích mặt bằng) không có dòng năm nên `_split_table_rows` không
  áp dụng được; nó vẫn ở dạng văn xuôi. q04, q25, q26, q27 đều đạt nên chưa đáng làm thêm.
- **Tiền tố metadata là bản rẻ của contextual retrieval** — dựng từ metadata thay vì gọi
  LLM sinh câu ngữ cảnh cho từng chunk. Đổi một phần chất lượng lấy chi phí build bằng 0.
- **Chưa có câu hỏi nào cần tổng hợp nhiều trang.** Cả 38 câu đều trả lời được từ một
  trang. Đó là giới hạn của bản trích 18 trang hơn là của hệ thống.
- **6 câu ngoài phạm vi vẫn là ít.** 6/6 chỉ cho khoảng tin cậy [61%, 100%].
