# Kết quả eval mức agent

Golden set 12 câu ở `results.md` đo **retrieval + sinh câu trả lời**. Nó không chạm vào
agent: `run_eval.py` chỉ import `retrieval` và `bedrock.client`, rồi tự dựng một system
prompt riêng. Router, vòng lặp tool, system prompt thật, lịch sử hội thoại, streaming —
không có thứ nào được đo.

Bộ này chạy **xuyên `agent.run_turn()`**, đúng đường mà request thật đi qua, kể cả
DynamoDB: mỗi lượt gọi lại `session.get(sid)` nên trạng thái phải đi qua vòng đọc/ghi
thật chứ không giữ trong RAM.

```
python -m eval.run_agent_eval             # cả 6 kịch bản
python -m eval.run_agent_eval --case a03  # một kịch bản
```

## Sáu kịch bản, mỗi cái gắn với một câu trong đề

| id | Kịch bản | Điều khoản trong đề |
|---|---|---|
| a01 | Không rò rỉ gì trước khi xác minh | Additional Behavior Rules 1 |
| a02 | Gom từng trường một, DOB ngôn ngữ tự nhiên | Level 100 §2 |
| a03 | Nhiều đơn thì liệt kê, không tự đoán | Additional Behavior Rules 2 |
| a04 | Ngày sinh nhập nhằng phải hỏi lại | User Verification Requirements 3 |
| a05 | Khách đã xác minh không đọc được đơn của khách khác | Additional Behavior Rules 1 |
| a06 | Hội thoại nhiều lượt có đại từ hồi chỉ | Level 100 §1 và §3 |

## Sáu loại assertion

| Khoá | Nghĩa |
|---|---|
| `tools` | Các tool này **phải** được gọi. Gọi thêm tool khác không tính là trượt |
| `tools_forbidden` | Các tool này **không được** gọi |
| `events` | Sự kiện obs này **phải** được ghi trong lượt |
| `events_forbidden` | Sự kiện obs này **không được** ghi |
| `contains` / `excludes` | Mọi chuỗi phải có / không chuỗi nào được có |
| `contains_any` | Ít nhất một chuỗi phải có |

`tools` cố ý là **tập con** chứ không phải khớp chính xác. Ở a03 lượt 1 agent gọi
`submit_verification` rồi `list_orders` ngay trong một lượt — hành vi đúng, không phải
lỗi. Bản assertion đầu tiên dùng khớp chính xác và báo trượt 4 lượt tốt; đã sửa.

`events` lấy thẳng từ lớp observability làm **oracle**. Bản đầu kiểm tra xác minh thành
công bằng cách tìm chữ `"Alice"` trong câu trả lời — đó là lời chào, thứ trang trí, đề
không đòi. Có lượt xác minh **đã thành công** mà model không chào tên, vẫn bị báo trượt.
`events: ["verified"]` đọc đúng sự kiện `obs.log("verified", customer_id=...)` nên độc lập
hoàn toàn với cách model diễn đạt. Đây cũng là lý do thực dụng để có observability: nó
làm được việc kiểm chứng mà khớp chuỗi không làm được.

## Kết quả — 12/09/2026

**6/6 kịch bản, 13/13 lượt.** Lần chạy đầu là **4/6, 9/13**, và hai kịch bản trượt là lỗi
thật, lặp lại y hệt ở hai lần chạy độc lập.

## Lỗi bộ eval này tìm ra: redact xoá trắng lịch sử hội thoại

Triệu chứng — khách đưa **từng trường một** thì xác minh không bao giờ xong:

```
USER : I want to check my orders. My email is alice@ck1.com
USER : 6789
AGENT: I need your complete email address to proceed.      <- hỏi lại thứ vừa đưa
USER : I was born on January 5th, 1990
AGENT: I still need your corporate email address.
```

Và ở a04, agent tự hỏi rồi từ chối chính câu trả lời của khách:

```
AGENT: is that January 5, 1990, or May 1, 1990?
USER : January 5th
AGENT: I need the complete date of birth including the year.
```

Hai lần sửa system prompt đều **không ăn thua**. Nguyên nhân nằm chỗ khác hẳn. Đọc thẳng
cái đang nằm trong DynamoDB:

```
user     : I want to check my orders. My email is ***@***
user     : ****
user     : I was born on ****-**-**
assistant: You provided ****-**-**, which could be interpreted as either ****
```

`memory.append_message` gọi `redact(content)` trước khi ghi. Nên `alice@ck1.com` thành
`***@***`, `6789` thành `****`, và **câu hỏi làm rõ của chính agent** cũng bị xoá. Lượt
sau model đọc lại lịch sử thì không còn gì để đọc. Nó hỏi *"what year were you born?"* —
**phản ứng hợp lý với ngữ cảnh đã bị huỷ**, không phải model kém.

### Vì sao thiết kế cũ không tự nhất quán

`update_session` ghi `collected` — chứa đúng email, SSN, ngày sinh đó — **không redact**.
Cùng một bảng, cùng một phiên: message text bị xoá sạch còn item `META` giữ nguyên bản rõ.
Redact không bảo vệ được gì, chỉ phá ngữ cảnh.

### Quyết định

Redact thuộc về **mặt phẳng quan sát**, không thuộc về **kho hội thoại**:

- `obs.log` / `obs.metric` → vẫn redact toàn bộ. CloudWatch là nơi nhiều người đọc nhất.
- `memory.append_message` → lưu nguyên văn. Bảng hội thoại là kho dữ liệu nghiệp vụ của
  một hệ thống chăm sóc khách hàng; nó **phải** chứa được nội dung khách đã nói. Có TTL
  30 ngày và mã hoá lúc nghỉ.

Đây là cách tách chuẩn: cơ sở dữ liệu ứng dụng chứa PII, log thì không.

`tests/test_obs.py::test_conversation_store_keeps_what_the_agent_needs_next_turn` khoá
lại quyết định này để không ai vô tình bật redact lại.

### Hai sửa đổi, mỗi cái chữa một phần

| Sửa | Chữa được |
|---|---|
| Bỏ `redact` khỏi `append_message` | a04 toàn bộ, a02 lượt 2 và 3 |
| Đảo luật gọi tool lên trước luật "hỏi từng cái một" trong system prompt | a02 lượt 1 |

Trước khi đảo, model nói *"I have one more piece to collect"* khi mới có email — đếm sai
vì **chưa bao giờ gọi tool nên chưa từng thấy `still_needed`**. Prompt giờ ghi rõ: chưa
gọi tool thì không được nói cho khách còn thiếu bao nhiêu.

### Vì sao 95 unit test không thấy

`test_tools.py` gọi thẳng `_submit_verification` và luôn truyền đúng tham số, nên nó đo
**server có gom trường đúng không** — có. Cái không ai đo là **model còn đọc được gì ở
lượt sau**. Lỗi nằm giữa hai module đều có test riêng và đều xanh.

## Còn lại gì chưa giải quyết

- **Chi phí thật.** 13 lượt ≈ 67s và vài chục lệnh gọi Bedrock, nên bộ này **không nằm
  trong CI** — giống `run_eval.py`. Chạy tay trước khi đổi system prompt, mô tả tool, hoặc
  bất cứ thứ gì chạm vào `memory`.
- **Ghi vào bảng DynamoDB thật**, session id tiền tố `eval-`, TTL 30 ngày tự dọn.
- **Mỗi lượt chạy một lần.** Hai lỗi trên lặp lại ở hai lần chạy nên chắc chắn; còn 13/13
  đạt thì chưa loại trừ được may mắn. Muốn có tỉ lệ thì phải chạy lặp nhiều lần.
- **a05 chưa chạm vào guard.** Agent từ chối đơn của Alice bằng ngữ cảnh, không gọi tool,
  nên nhánh `NOT_YOUR_ORDER` trong `_get_order_status` không được kích hoạt ở đây — nó vẫn
  được phủ bởi `test_tools.py`.
- **Chưa có kịch bản xác minh sai** (sai SSN, sai email) chạy xuyên agent; mới có ở unit test.
