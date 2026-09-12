# Sơ đồ kiến trúc — bài test Solution Engineer Intern @ Cloud Kinetics

Sinh bằng thư viện [`diagrams`](https://diagrams.mingrammer.com/) (icon AWS chính chủ) + Graphviz.
Mỗi sơ đồ xuất 2 định dạng: **PNG** để chèn slide, **SVG** để phóng to không vỡ.

| File | Dùng cho slide nào | Nội dung |
|---|---|---|
| `1-kien-truc-runtime.png` | Slide kiến trúc (Level 100 + 200) | Đường đi một câu hỏi: trình duyệt → **CloudFront + OAC** (ký SigV4 hộ) → Function URL `AWS_IAM` `RESPONSE_STREAM` → agent loop → Bedrock. Mũi tên **đỏ đậm "CHỈ khi đã verify"** là điểm cần dừng lại giải thích; đường **đứt cam** cho thấy router chạy trên thread, ngoài đường tới hạn. |
| `2-pipeline-du-lieu.png` | Slide Level 300 #5 | v1 chunk ngây thơ (làm vỡ bảng, mất dòng năm) đặt cạnh v2 (bỏ boilerplate → tách bảng → LLM diễn giải → chunk theo section), cùng đổ về `run_eval.py` để ra **bảng số trước/sau**. |
| `3-cicd-iac.png` | Slide Level 200 | GitHub Actions → OIDC AssumeRole (không key tĩnh) → Terraform apply → toàn bộ hạ tầng. |

> **Sơ đồ 1 đã vẽ lại ngày 12/09/2026 sau khi triển khai thật.** Bản cũ (09/09) vẽ trước khi
> build nên sai 5 chỗ: thiếu CloudFront, ghi nhầm Opus 5 cho hội thoại (thật ra Haiku 4.5) và
> Haiku cho router (thật ra Nova Lite), để index ở S3 (thật ra nướng trong container image),
> và để customers/orders ở DynamoDB (thật ra là file JSON trong image).

## Vẽ lại

```bash
pip install diagrams          # cần Graphviz: https://graphviz.org/download/
python ve_so_do.py            # ghi đè cả 6 file PNG/SVG
```

Chạy được cả trên Windows lẫn WSL/Linux — script tự chọn font theo `os.name`.

## Hai cái bẫy đã xử lý sẵn trong script

1. **Graphviz cài rồi mà vẫn báo `ExecutableNotFound`.** Sửa `os.environ["PATH"]` trong Python **không đủ** cho `diagrams` — script ép thẳng `dot_command.DOT_BINARY` tới `dot.exe`. Máy này Graphviz nằm ở `C:\Program Files\Graphviz\bin`.
2. **Chữ tiếng Việt mất dấu.** Font mặc định của Graphviz không đủ bộ dấu. Script chọn `Segoe UI` trên Windows và `DejaVu Sans` trên Linux/WSL — cả hai đều đủ dấu. **Đổi font thì phải mở file PNG ra nhìn**, vì thiếu dấu không gây lỗi, nó chỉ lặng lẽ render sai.

## Muốn sửa

- **Đổi chữ / thêm node:** sửa trực tiếp trong `ve_so_do.py`, mỗi sơ đồ là một khối `with Diagram(...)`.
- **Sơ đồ bị kéo dài dọc:** thường do một cụm có nhiều node không nối với nhau. Cách chữa đã dùng ở sơ đồ 3: nối chúng bằng cạnh vô hình `Edge(style="invis")` để ép xếp thành hàng ngang.
- **Nhãn mũi tên trôi ra chỗ trống:** rút ngắn nhãn, hoặc thêm `constraint="false"` cho cạnh cắt ngang nhiều cụm.
- **Cần bản kéo-thả để sửa tay:** import file SVG vào draw.io (`File → Import`), hoặc dựng lại bằng thư viện shape AWS 2025 có sẵn trong draw.io.
