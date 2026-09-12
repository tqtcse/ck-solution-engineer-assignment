"""Sinh 3 sơ đồ kiến trúc cho bài test Solution Engineer Intern @ Cloud Kinetics.

    python ve_so_do.py

Xuất ra (PNG để chèn slide + SVG để phóng to không vỡ):
    1-kien-truc-runtime.png    — kiến trúc lúc chạy (Level 100 + 200)
    2-pipeline-du-lieu.png     — ingestion & preprocessing v1 vs v2 (Level 300 #5)
    3-cicd-iac.png             — CI/CD + Infrastructure as Code (Level 200)

Yêu cầu: pip install diagrams  +  Graphviz (https://graphviz.org/download/)
"""

import os
import pathlib
import shutil

# Graphviz cài ở Program Files nhưng không nằm trong PATH.
# Sửa os.environ["PATH"] KHÔNG đủ cho diagrams -> phải ép thẳng đường dẫn dot.exe.
_dot = shutil.which("dot")
if _dot is None:
    for _p in (r"C:\Program Files\Graphviz\bin", r"C:\Program Files (x86)\Graphviz\bin"):
        _cand = pathlib.Path(_p) / "dot.exe"
        if _cand.is_file():
            os.environ["PATH"] = _p + os.pathsep + os.environ["PATH"]
            _dot = str(_cand)
            break
if _dot is None:
    raise SystemExit("Không tìm thấy Graphviz. Cài tại https://graphviz.org/download/")
try:  # graphviz >= 0.20
    from graphviz.backend import dot_command

    dot_command.DOT_BINARY = pathlib.Path(_dot)
except ImportError:  # bản cũ hơn
    from graphviz.backend import execute as _gv_execute

    _gv_execute.DOT_BINARY = pathlib.Path(_dot)

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR, Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.management import Cloudwatch, CloudwatchAlarm, CloudwatchLogs
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import CloudFront
from diagrams.aws.security import IAMRole, KMS
from diagrams.aws.storage import S3
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import User, Users
from diagrams.onprem.iac import Terraform
from diagrams.onprem.vcs import Github
from diagrams.programming.framework import Fastapi
from diagrams.generic.storage import Storage
from diagrams.programming.language import Python

# Segoe UI chi co tren Windows. Tren Linux/WSL phai doi sang mot font
# CO DAY DU DAU TIENG VIET, neu khong chu se mat dau (DejaVu Sans co).
FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"

GRAPH = {
    "fontname": FONT,
    "fontsize": "22",
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.45",
    "ranksep": "1.0",
    "compound": "true",
}
NODE = {"fontname": FONT, "fontsize": "11"}
EDGE = {"fontname": FONT, "fontsize": "10", "color": "#4A5568"}


def box(bg, pen, fg="#1A365D"):
    return {
        "fontname": FONT,
        "fontsize": "13",
        "bgcolor": bg,
        "pencolor": pen,
        "fontcolor": fg,
        "style": "rounded,dashed",
        "penwidth": "1.8",
        "margin": "20",
    }


AWS = {**box("#FFFFFF", "#232F3E", "#232F3E"), "style": "rounded"}
APP = box("#EAF2FE", "#2B6CB0")
RUNTIME = box("#D9E8FB", "#2B6CB0")
MODEL = box("#F3E8FF", "#7C3AED", "#5B21B6")
DATA = box("#E6FFFA", "#2C7A7B", "#1D4044")
OPS = box("#FFF5F5", "#C53030", "#742A2A")
INGEST = box("#FFF7E6", "#DD6B20", "#7B341E")
BAD = box("#FFF5F5", "#C53030", "#742A2A")
GOOD = box("#F0FFF4", "#276749", "#22543D")
CICD = box("#F7FAFC", "#4A5568", "#2D3748")

PURPLE = "#7C3AED"
TEAL = "#2C7A7B"
BLUE = "#2B6CB0"
RED = "#C53030"
ORANGE = "#DD6B20"
GREEN = "#276749"


# ──────────────────────────────────────────────────────────────────────────
# 1. Kiến trúc lúc chạy
#    Cập nhật 12/09/2026 sau khi triển khai thật — sơ đồ cũ vẽ trước khi build
#    nên sai 5 chỗ: thiếu CloudFront, sai tên model, index nằm trong image chứ
#    không ở S3, customers/orders là file JSON chứ không phải DynamoDB, và
#    router chạy song song chứ không nối tiếp.
# ──────────────────────────────────────────────────────────────────────────
with Diagram(
    "1 · Kiến trúc runtime — Agentic Conversational System trên AWS",
    filename="1-kien-truc-runtime",
    show=False,
    direction="LR",
    outformat=["png", "svg"],
    graph_attr=GRAPH,
    node_attr=NODE,
    edge_attr=EDGE,
):
    users = Users("Khách hàng\ntrình duyệt")

    with Cluster("AWS Cloud · us-east-1 · serverless, không VPC/NAT", graph_attr=AWS):

        cdn = CloudFront("CloudFront + OAC\nký SigV4 hộ người xem")

        with Cluster("AWS Lambda — container image, scale-to-zero", graph_attr=APP):
            fn = Lambda("Function URL\nAWS_IAM · RESPONSE_STREAM")

            with Cluster("Agent runtime", graph_attr=RUNTIME):
                api = Fastapi("FastAPI + LWA\nSSE /chat/stream")
                agent = Python("Agent loop\ntool use · tối đa 6 bước")
                tools = Python("Tools + GUARDRAIL\nkb_search · verify · orders")
                api >> Edge(color=BLUE, penwidth="2.0") >> agent
                agent >> Edge(color=BLUE, penwidth="2.0") >> tools

            with Cluster("Nướng sẵn trong image", graph_attr=DATA):
                index = Storage("index_v2.npz + chunks\nINDEX_VERSION đổi được")
                oms = Storage("customers.json\norders.json — mock OMS")

            router = Python("Router intent\nluật → state → model")

        with Cluster("Amazon Bedrock", graph_attr=MODEL):
            haiku = Bedrock("Claude Haiku 4.5\nhội thoại + tool use")
            nova = Bedrock("Nova Lite\nphân loại intent")
            titan = Bedrock("Titan Embeddings v2\n1024 chiều, chuẩn hoá")

        with Cluster("Dữ liệu phiên", graph_attr=DATA):
            ddb_conv = Dynamodb("DynamoDB · conversations\nsingle-table · GSI1 · TTL 30 ngày")

        with Cluster("Quan sát", graph_attr=OPS):
            logs = CloudwatchLogs("Logs JSON\ntrace_id · session_id · PII đã che")
            metrics = Cloudwatch("EMF metrics\nTTFT · token · RetrievalTop1")
            alarm = CloudwatchAlarm("3 Alarms\nErrors · p95 · Bedrock 429")
            logs >> Edge(color=RED) >> metrics >> Edge(color=RED) >> alarm

        ecr = ECR("ECR\nimage tag = commit sha")

    users >> Edge(label="HTTPS + SSE\nx-amz-content-sha256", color=BLUE, penwidth="2.2") >> cdn
    cdn >> Edge(label="SigV4", color=BLUE, penwidth="2.2") >> fn
    fn >> Edge(color=BLUE, penwidth="2.2") >> api

    agent >> Edge(label="stream", color=PURPLE, penwidth="2.0") >> haiku
    tools >> Edge(label="embed", color=PURPLE) >> titan

    api >> Edge(label="thread — NGOÀI đường tới hạn", color=ORANGE,
                style="dashed", constraint="false") >> router
    router >> Edge(color=PURPLE, style="dashed", constraint="false") >> nova

    tools >> Edge(label="top-k cosine", color=TEAL) >> index
    tools >> Edge(label="CHỈ khi đã verify", color=RED, penwidth="2.4") >> oms
    agent >> Edge(label="lịch sử phiên", color=TEAL) >> ddb_conv

    tools >> Edge(color=RED, style="dotted") >> logs
    ecr >> Edge(label="image", color=GREEN, style="dashed", constraint="false") >> fn


# ──────────────────────────────────────────────────────────────────────────
# 2. Pipeline dữ liệu: v1 ngây thơ vs v2 cải tiến
# ──────────────────────────────────────────────────────────────────────────
with Diagram(
    "2 · Pipeline dữ liệu — vì sao retrieval sai và sửa thế nào (Level 300 #5)",
    filename="2-pipeline-du-lieu",
    show=False,
    direction="LR",
    outformat=["png", "svg"],
    graph_attr={**GRAPH, "ranksep": "1.2"},
    node_attr=NODE,
    edge_attr=EDGE,
):
    with Cluster("Nguồn", graph_attr=INGEST):
        raw = S3("S3 · tài liệu gốc\nCompany-10k-18pages.pdf\n(10-K Amazon FY2019)")

    with Cluster("v1 — chunk ngây thơ  (BASELINE)", graph_attr=BAD):
        v1_ex = Python("PyMuPDF\nlấy text thô")
        v1_ch = Python("Chunk cố định\n800 ký tự · overlap 100")
        v1_ex >> Edge(color=RED) >> v1_ch

    with Cluster("v2 — pipeline cải tiến", graph_attr=GOOD):
        v2_clean = Python("Bỏ boilerplate\n'Table of Contents' ×18\n+ số trang")
        v2_struct = Python("Nhận diện cấu trúc\nItem 1/1A/2/6 + tiêu đề\nrisk factor")
        v2_table = Python("Tách bảng riêng\n-> Markdown giữ header cột")
        v2_llm = Bedrock("LLM diễn giải bảng\n'net sales 2019 = $280,522M'")
        v2_chunk = Python("Chunk theo section\n400–800 token · metadata\n(item, page, is_table)")
        v2_clean >> Edge(color=GREEN) >> v2_struct >> Edge(color=GREEN) >> v2_table
        v2_table >> Edge(color=GREEN) >> v2_llm >> Edge(color=GREEN) >> v2_chunk

    embed = Bedrock("Titan Embeddings v2")

    with Cluster("Chỉ mục", graph_attr=DATA):
        idx1 = S3("index_v1.npz")
        idx2 = S3("index_v2.npz")

    with Cluster("Đo lường", graph_attr=OPS):
        golden = Python("golden_set.yaml\n15–20 câu (có câu số liệu\ntrong bảng)")
        runner = Python("run_eval.py\nhit@3 · answer_correct\ngrounded · refusal")
        report = Python("results.md\nBẢNG SỐ TRƯỚC / SAU")
        golden >> Edge(color=RED) >> runner >> Edge(color=RED) >> report

    raw >> Edge(color=RED, label="lỗi: bảng vỡ, mất dòng năm") >> v1_ex
    raw >> Edge(color=GREEN) >> v2_clean
    v1_ch >> Edge(color=RED) >> embed
    v2_chunk >> Edge(color=GREEN) >> embed
    embed >> Edge(color=RED, style="dashed") >> idx1
    embed >> Edge(color=GREEN) >> idx2
    idx1 >> Edge(color="#718096", style="dashed") >> runner
    idx2 >> Edge(color="#718096") >> runner


# ──────────────────────────────────────────────────────────────────────────
# 3. CI/CD + IaC
# ──────────────────────────────────────────────────────────────────────────
with Diagram(
    "3 · CI/CD + Infrastructure as Code (Level 200)",
    filename="3-cicd-iac",
    show=False,
    direction="LR",
    outformat=["png", "svg"],
    graph_attr=GRAPH,
    node_attr=NODE,
    edge_attr=EDGE,
):
    dev = User("Dev")

    with Cluster("GitHub · pipeline", graph_attr=CICD):
        repo = Github("Repository")
        ci = GithubActions("CI · pull request\nruff + pytest\n(+ eval golden set)")
        cd = GithubActions("CD · push main\nbuild → push → apply")
        tf = Terraform("Terraform\nmodule tái dùng")
        repo >> Edge(color=BLUE) >> ci
        repo >> Edge(color=BLUE) >> cd
        cd >> Edge(color=BLUE) >> tf

    with Cluster("AWS Cloud", graph_attr=AWS):
        role = IAMRole("IAM Role cho OIDC\nkhông có access key tĩnh")

        with Cluster("Hạ tầng do Terraform quản lý (một lệnh apply)", graph_attr=APP):
            ecr = ECR("Amazon ECR")
            fn = Lambda("Lambda +\nFunction URL")
            ddb = Dynamodb("DynamoDB × 2")
            s3d = S3("S3 · vector index")
            cw = CloudwatchLogs("CloudWatch\nretention 7 ngày")
            kms = KMS("KMS")
            tf_state = S3("S3 · tfstate\n(có khoá state)")
            # cạnh vô hình -> ép xếp thành hàng ngang cho gọn
            ecr >> Edge(label="deploy image", color=BLUE, style="dashed") >> fn
            fn >> Edge(style="invis") >> ddb >> Edge(style="invis") >> s3d
            s3d >> Edge(style="invis") >> cw >> Edge(style="invis") >> kms
            kms >> Edge(style="invis") >> tf_state

    dev >> Edge(color=BLUE) >> repo
    cd >> Edge(label="OIDC AssumeRole\n(không key tĩnh)", color=RED, penwidth="2.2") >> role
    cd >> Edge(label="docker push", color=BLUE) >> ecr
    tf >> Edge(label="terraform apply", color=ORANGE, penwidth="2.2") >> fn

print("Đã sinh 3 sơ đồ (PNG + SVG) trong", os.getcwd())
