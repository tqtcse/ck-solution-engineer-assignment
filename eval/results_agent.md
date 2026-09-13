# Kết quả eval mức agent

Golden set 12 câu ở `results.md` đo **retrieval + sinh câu trả lời**. Nó không chạm
vào agent: `run_eval.py` chỉ import `retrieval` và `bedrock.client`, rồi tự dựng một
system prompt riêng. Router, vòng lặp tool, system prompt thật, lịch sử hội thoại,
streaming — không có thứ nào được đo.

Bộ này chạy **xuyên `agent.run_turn()`**, tức đúng đường mà request thật đi qua, kể cả
DynamoDB: mỗi lượt gọi lại `session.get(sid)` nên trạng thái phải đi qua vòng đọc/ghi
thật, không giữ trong RAM.

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

## Bốn loại assertion

| Khoá | Nghĩa |
|---|---|
| `tools` | Các tool này **phải** được gọi. Gọi thêm tool khác không tính là trượt |
| `tools_forbidden` | Các tool này **không được** gọi |
| `contains` / `excludes` | Mọi chuỗi phải có / không chuỗi nào được có |
| `contains_any` | Ít nhất một chuỗi phải có |

`tools` cố ý là **tập con** chứ không phải khớp chính xác. Ở a03 lượt 1 agent gọi
`submit_verification` rồi `list_orders` ngay trong một lượt — đó là hành vi đúng, không
phải lỗi. Bản assertion đầu tiên dùng khớp chính xác và báo trượt 4 lượt tốt; đã sửa.

`excludes` là assertion an toàn, `tools_forbidden` là assertion hành vi. Ở a03 lượt 2
`tools_forbidden: [get_order_status]` mã hoá đúng câu *"must not assume which order the
user wants"* — agent được phép trả lời từ ngữ cảnh, nhưng không được tự chọn một đơn.

## Kết quả — 12/09/2026

**4/6 kịch bản, 9/13 lượt.** Hai kịch bản trượt là **lỗi thật**, đã lặp lại y hệt ở hai
lần chạy độc lập.

### Lỗi 1 — email bị nuốt, xác minh không bao giờ xong (a02)

Khi khách đưa **từng trường một**, lượt đầu agent **không gọi** `submit_verification`:

```
USER : I want to check my orders. My email is alice@ck1.com
AGENT: Thank you for providing your email. ... Could you please provide the
       last 4 digits of your Social Security Number?
tools: []
```

Email không bao giờ tới server, `state.collected` vẫn rỗng. Hậu quả dây chuyền:

```
USER : 6789
AGENT: I still need two more pieces... Could you please provide your
       corporate email address?          <- hỏi lại thứ khách vừa đưa
USER : I was born on January 5th, 1990
AGENT: I still need your corporate email address to complete the verification.
```

Khách đã đưa đủ cả ba trường mà vẫn kẹt. Mô tả tool ghi rõ *"Call this as soon as the
customer provides ANY of the three items, one at a time"* — model bỏ qua ở lượt 1.

Kịch bản a03 đưa cả ba trường **trong một câu** thì xác minh xong ngay. Nên lỗi chỉ lộ
ra ở đường đi từng-trường-một, và đề yêu cầu đúng đường đó: *"Missing information (ask
follow-up questions)"*.

### Lỗi 2 — hỏi lại ngày sinh nhập nhằng rồi từ chối chính câu trả lời (a04)

Server xử lý nhập nhằng đúng:

```
USER : alice@ck1.com, ssn 6789, dob 05/01/1990
AGENT: is that January 5, 1990, or May 1, 1990?
```

Nhưng khách trả lời tự nhiên thì bị chặn:

```
USER : January 5th
AGENT: I need the full date including the year.
LOG  : verify_failed reason=unparseable attempts=1
```

Agent tự hỏi "January 5 hay May 1?" rồi từ chối "January 5th". Năm **1990 đang nằm sẵn
trong ngữ cảnh** — model chỉ cần gửi lại đủ ngày. Đề nói thẳng: *"handle flexible DOB
input gracefully (no strict format enforcement)"*.

### Vì sao 95 unit test không thấy hai lỗi này

`test_tools.py` gọi thẳng `_submit_verification` và luôn truyền đúng tham số, nên nó đo
**server có gom trường đúng không** — có. Cái không ai đo là **model có chịu gửi trường
đó đi không**. Lỗi nằm ở quyết định của model, chỉ lộ ra khi chạy thật.

## Còn lại gì chưa giải quyết

- **Chi phí thật.** 13 lượt ≈ 65s và vài chục lệnh gọi Bedrock, nên bộ này **không nằm
  trong CI** — giống `run_eval.py`. Chạy tay trước khi đổi system prompt hoặc mô tả tool.
- **Ghi vào bảng DynamoDB thật**, session id tiền tố `eval-`, TTL 30 ngày tự dọn.
- **Chưa đo lại nhiều lần để lấy tỉ lệ.** Mỗi lượt chạy một lần; hai lỗi trên lặp lại ở
  cả hai lần chạy nên chắc chắn, còn 9 lượt đạt thì chưa loại trừ được may mắn.
- **a05 chưa chạm vào guard.** Agent từ chối đơn của Alice bằng ngữ cảnh, không gọi tool,
  nên nhánh `NOT_YOUR_ORDER` trong `_get_order_status` không được kích hoạt ở đây — nó
  vẫn được phủ bởi `test_tools.py`.
