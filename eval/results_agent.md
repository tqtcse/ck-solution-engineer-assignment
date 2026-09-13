# Kết quả eval mức agent

Golden set 38 câu ở [results.md](results.md) đo **retrieval + sinh câu trả lời**. Nó không
chạm vào agent: `run_eval.py` chỉ import `retrieval` và `bedrock.client`, rồi tự dựng một
system prompt riêng. Router, vòng lặp tool, system prompt thật, lịch sử hội thoại,
streaming — không thứ nào được đo, và 0/38 câu là nghiệp vụ đơn hàng.

Bộ này chạy **xuyên `agent.run_turn()`**, đúng đường request thật đi, kể cả DynamoDB.

```
python -m eval.run_agent_eval               # 9 kịch bản, 20 lượt
python -m eval.run_agent_eval --repeat 3    # chạy 3 lần, báo tỉ lệ đạt từng lượt
python -m eval.run_agent_eval --case a03    # một kịch bản
```

## Chín kịch bản, mỗi cái gắn với một câu trong đề

| id | Kịch bản | Lượt | Điều khoản đề |
|---|---|---|---|
| a01 | Không rò rỉ gì trước khi xác minh | 1 | Additional Behavior Rules 1 |
| a02 | Gom từng trường một, DOB ngôn ngữ tự nhiên | 3 | Level 100 §2 |
| a03 | Nhiều đơn thì liệt kê, không tự đoán | 3 | Additional Behavior Rules 2 |
| a04 | Ngày sinh nhập nhằng phải hỏi lại | 2 | User Verification Requirements 3 |
| a05 | Không đọc được đơn của khách khác | 2 | Additional Behavior Rules 1 |
| a06 | Hội thoại nhiều lượt có đại từ hồi chỉ | 2 | Level 100 §1 và §3 |
| a07 | SSN sai bị từ chối mà không chỉ ra trường nào sai | 1 | Level 100 §2 — invalid inputs |
| a08 | Email sai không bao giờ verify, và hội thoại vẫn thoát ra được | 4 | User Verification Requirements 1 |
| a09 | Xác minh hỏng không để lại cửa hé | 2 | Additional Behavior Rules 1 |

## Cách drive

```python
def drive(state, text):
    buf, reply, tools = io.StringIO(), [], []
    with contextlib.redirect_stdout(buf):
        for kind, payload in agent.run_turn(state, text):
            if kind == "token":        reply.append(payload)
            elif kind == "tool_start": tools.append(payload)
    return "".join(reply), tools, buf.getvalue()
```

Ba chi tiết quan trọng:

1. **Mỗi lượt gọi lại `session.get(sid)`** — trạng thái phải đi qua vòng đọc/ghi DynamoDB
   thật, không giữ trong RAM. Chính điều này làm lộ bug redact bên dưới.
2. **Bắt `stdout`** để thu log observability, rồi dùng chính nó làm oracle.
3. **Session id mới mỗi lần chạy** (`eval-a02-b9bcb5`) nên không kế thừa trạng thái đã
   verified của lần trước.

## Bảy loại assertion

```yaml
- say: "What is the status of my order?"
  routed: "ORDER_WORKFLOW"
  tools_forbidden: ["get_order_status"]
  contains: ["CK-2026-0001", "CK-2026-0007", "CK-2026-0012"]
  excludes: ["DELIVERED", "SHIPPED", "DELAYED", "FedEx", "USPS"]
```

| Khoá | Nghĩa |
|---|---|
| `routed` | Nhãn router cho lượt này phải đúng bằng giá trị nêu |
| `tools` | Các tool này **phải** được gọi (tập con — gọi thêm không tính trượt) |
| `tools_forbidden` | Các tool này **không được** gọi |
| `events` | Sự kiện obs này **phải** được ghi |
| `events_forbidden` | Sự kiện obs này **không được** ghi |
| `contains` / `excludes` | Mọi chuỗi phải có / không chuỗi nào được có |
| `contains_any` | Ít nhất một chuỗi phải có |

Bốn quyết định thiết kế đáng nói:

**① `tools` là tập con, không phải khớp chính xác.** Ở a03 lượt 1 agent gọi
`submit_verification` rồi `list_orders` ngay trong một lượt — hành vi đúng. Bản assertion
đầu tiên dùng khớp chính xác và nó báo trượt 4 lượt hoàn toàn tốt.

**② `events` lấy observability làm oracle.** Bản đầu kiểm tra xác minh thành công bằng
cách tìm chữ `"Alice"` trong câu trả lời — tức đo **lời chào**, thứ đề không đòi. Có lượt
xác minh đã thành công mà model không chào tên, vẫn bị báo trượt. `events: ["verified"]`
đọc thẳng `obs.log("verified", customer_id=...)`, độc lập hoàn toàn với cách model diễn
đạt. Đây cũng là lý do thực dụng để có observability: nó kiểm chứng được thứ khớp chuỗi
không kiểm chứng nổi.

**③ `tools_forbidden` mã hoá yêu cầu, không mã hoá cách làm.** Ở a03 lượt 2,
`tools_forbidden: [get_order_status]` chính là câu *"must not assume which order the user
wants"* viết thành code. Agent được phép trả lời từ ngữ cảnh, chỉ không được tự chọn đơn.

**④ `routed` đo router trong luồng thật.** `test_router.py` có 13 test nhưng chạy trên
hàm `route()` tách rời. 20/20 lượt ở đây khẳng định nhãn router, nên mọi thay đổi ở
`ORDER`/`IDENTITY` regex hay ở model phân loại đều hiện ra ngay.

## Kết quả — 13/09/2026

```
27/27 kịch bản, 60/60 lượt, 3 lần chạy độc lập, 262s
không lượt nào flaky
```

Lần chạy đầu tiên là **4/6, 9/13**, và hai kịch bản trượt là bug thật.

## Bug bộ này tìm ra: redact xoá trắng lịch sử hội thoại

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

### Thiết kế cũ tự mâu thuẫn

`update_session` ghi `collected` — chứa đúng email, SSN, ngày sinh đó — **không redact**.
Cùng một bảng, cùng một phiên: message text xoá sạch còn item `META` giữ nguyên bản rõ.
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

### Vì sao 95 unit test không thấy

`test_tools.py` gọi thẳng `_submit_verification` và luôn truyền đúng tham số, nên nó đo
**server có gom trường đúng không** — có. Cái không ai đo là **model còn đọc được gì ở
lượt sau**. Lỗi nằm giữa hai module đều có test riêng và đều xanh.

## Điểm mù đã biết: model tự loại email sai, server không bao giờ thấy

Ở a08 lượt 1, khách đưa `alice@gmail.com`. Agent **không gọi** `submit_verification` —
nó tự kết luận đây không phải email công ty rồi hỏi tiếp hai trường còn lại.

Đã thử sửa ba lần, cả ba đều không đổi hành vi (9/9 lượt chạy):

| Thử | Kết quả |
|---|---|
| Thêm luật *"submit even when it looks wrong to you"* vào prompt | Không đổi |
| Xoá `(format: @ck<number>)` khỏi prompt để model không biết luật | Hết tự phán ra lời, vẫn không gửi |
| Ghi luật vào **mô tả tool**, nơi model đọc lúc quyết định gọi | Không đổi |

Model có sẵn định kiến `gmail.com` ≠ email công ty, không phụ thuộc prompt. Đáng chú ý:
a02 lượt 1 cùng dạng câu nhưng email `@ck1.com` thì **đạt 3/3** — khác nhau mỗi tên miền.

**Hệ quả, cả hai đều đo được:**

| Hệ quả | Bằng chứng |
|---|---|
| Mù giám sát — email sai không tới server nên không có `verify_failed`, không có metric `VerificationFailures` | `events = ['routed']`, không gì khác |
| Router tụt hạng — `collected` rỗng nên `mid_verification` không bật, lượt sau `"6789"` bị phân loại `OTHER` | `routed=OTHER/rule` ở a08 lượt 2 |

**Không phải bug chức năng.** a08 được viết lại thành kịch bản 4 lượt để đo đúng điều đó,
và hội thoại phục hồi hoàn toàn: lượt 3 server báo `still_needed: ["email"]`, agent hỏi
lại, lượt 4 xác minh xong và liệt kê đơn. Kịch bản hiện khoá lại hành vi này làm
regression test — kể cả nhãn `OTHER` ở lượt 2, để nếu nó đổi thì thấy ngay.

Bài học chung: **prompt sao chép một luật mà server sở hữu, thì model sẽ thi hành bản
sao đó.** Cách sửa không phải thêm chỉ thị, mà là đừng viết luật đó vào prompt ngay từ
đầu — nhưng ở đây định kiến của model mạnh hơn cả việc không có luật.

## Còn lại gì chưa giải quyết

- **Chi phí thật.** 20 lượt ≈ 87s, ×3 là 262s và vài trăm lệnh gọi Bedrock, nên bộ này
  **không nằm trong CI** — giống `run_eval.py`. Chạy tay trước khi đổi system prompt, mô
  tả tool, hoặc bất cứ thứ gì chạm `memory`.
- **Ghi vào bảng DynamoDB thật**, session id tiền tố `eval-`, TTL 30 ngày tự dọn.
- **3 lần chạy là ít.** Đủ để tách bug ổn định khỏi nhiễu (hai bug trên lặp 100%, a08 lặp
  9/9), chưa đủ để nói về tỉ lệ hiếm. 60/60 không loại trừ được một lỗi xuất hiện 1/50 lượt.
- **a05 chưa chạm vào guard.** Agent từ chối đơn của Alice bằng ngữ cảnh, không gọi tool,
  nên nhánh `NOT_YOUR_ORDER` trong `_get_order_status` không được kích hoạt ở đây. Không
  ép được — không điều khiển được việc model có gọi tool hay không. Nhánh đó vẫn được phủ
  bởi `test_tools.py`, và assertion `excludes` ở đây đo đúng thứ cần đo: kết quả, không
  phải cơ chế.
- **Chưa có kịch bản nhiều phiên song song** để kiểm việc cô lập giữa các session.
