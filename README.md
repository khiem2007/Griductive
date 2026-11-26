# Griductive Solver — CSC14003, Project 2

Đồ án **Nhập môn Trí tuệ nhân tạo**: xây dựng trò chơi Griductive và bộ giải suy luận bằng logic mệnh đề, mã hóa CNF và thuật toán DPLL tự cài đặt.

**Cập nhật tiến độ ngày 26/11/2026.** Mã hóa CNF, DPLL và Logic Agent đã hoạt động qua API Python. Agent giải được **15/15 puzzle** từ thông tin công khai. Khi kiểm tra riêng toàn bộ clue, **13/15 puzzle có đúng một nghiệm**.

> `python main.py` mở **Manual practice — answer check**. GUI lật thẻ nếu lựa chọn khớp đáp án, kể cả khi người chơi đoán. **Hint** và **Auto Solve** vẫn bị vô hiệu hóa. Chế độ chứng minh đã chạy qua API, còn yêu cầu chơi không đoán trên GUI của đề chưa được đáp ứng trong luồng khởi động mặc định.

## 1. Tài liệu và phạm vi

- Đề học phần quy định yêu cầu, tiêu chí đánh giá và quy cách nộp bài. [AI - Project 2.pdf](<AI - Project 2.pdf>)
- Mốc luyện tập thủ công sau Step 1 dành thuật toán tự động cho sinh viên. Các mô-đun solver hiện đã có phần triển khai. [AGENTS.md](AGENTS.md)

Theo `AGENTS.md`, puzzle chơi được do người dùng chuẩn bị và lựa chọn. Ứng dụng hỗ trợ khởi động khi chưa có puzzle, không ghi đè puzzle trong lúc chơi và hoạt động ở chế độ thủ công mà không cần import `solver`.

## 2. Yêu cầu của đồ án

### 2.1. Luật chơi và nguyên tắc suy luận

Theo đề, trang 1–4:

- Bàn cờ có kích thước 3×3, 4×4 hoặc 5×5; mỗi ô chứa một nhân vật, nghề nghiệp, trạng thái `CRIMINAL`/`INNOCENT` và một clue có cấu trúc.
- Cột đặt tên từ `A`, hàng đánh số từ `1`, từ trên xuống dưới. Đề yêu cầu nhân vật theo thứ tự tên hiển thị; tên/nghề không tự mang ý nghĩa logic.
- Ban đầu chỉ một số thẻ được mở. Clue đã mở luôn đúng, kể cả khi chủ thẻ là tội phạm.
- Agent chỉ dùng clue đã mở và trạng thái đã chứng minh. Không được đọc đáp án hay clue chưa mở để suy luận.
- Kết luận được chấp nhận khi đúng trong **mọi mô hình** của tri thức hiện tại; tìm được một mô hình SAT chưa đủ để kết luận.
- Khi chấp nhận một kết luận, chỉ mở thẻ tương ứng rồi bổ sung trạng thái và clue mới vào tri thức.
- Nếu cả hai trạng thái đều còn có thể xảy ra, trả `UNKNOWN` và không đoán. Nếu tri thức mâu thuẫn, trả `INCONSISTENT`.
- Puzzle hợp lệ phải có đúng một nghiệm hoàn chỉnh. Tính duy nhất của toàn bộ clue và khả năng giải từng bước không đoán cần được kiểm tra riêng.

Với biến `C_i = True` nghĩa là nhân vật `i` là tội phạm:

```text
KB_t = CNF(clue đã mở) AND các unit clause của trạng thái đã chứng minh

KB_t AND C_i          KB_t AND NOT C_i       Kết luận
SAT                   UNSAT                  CRIMINAL
UNSAT                 SAT                    INNOCENT
SAT                   SAT                    UNKNOWN
UNSAT                 UNSAT                  INCONSISTENT
```

### 2.2. Các hạng mục được đánh giá

| Hạng mục trong đề | Điểm | Tiến độ đã kiểm chứng |
| --- | ---: | --- |
| §4.1 Game có GUI | 10 | Có bàn cờ, tọa độ, tên/nghề, trạng thái và clue đã mở, highlight, Load và Restart. Engine tách khỏi Agent. GUI kiểm tra đáp án theo mặc định. Luồng kiểm chứng logic đã chạy khi inject Agent trực tiếp, còn Hint và Auto Solve chưa kết nối với nút bấm. |
| §4.2 Biểu diễn logic và CNF | 10 | Có ánh xạ biến xác định, kiểm tra clue/vùng, đánh giá ngữ nghĩa trực tiếp, mã hóa tự động và unit clause từ thẻ mở. API trả số biến chính/phụ và số mệnh đề. Đã kiểm thử sáu loại cốt lõi cùng hai mở rộng `PARITY` và `COMPARE`, có hỗ trợ vùng `BOUNDARY` và `INTERSECTION`. |
| §4.3 DPLL tự cài đặt | 10 | Có lan truyền đơn vị, phát hiện xung đột, chọn biến xác định, phân nhánh đệ quy và quay lui, kết quả SAT kèm phép gán đầy đủ hoặc UNSAT, timeout và thống kê. Đã chạy test đối chiếu vét cạn trên CNF nhỏ. |
| §4.4 Logic Agent | 20 | Có phân loại, chọn kết luận bắt buộc, cập nhật KB qua từng thẻ mở, trace, Hint qua API và kiểm tra duy nhất riêng. Đã giải 15/15 màn từ trạng thái công khai và tìm thấy 2 màn có nhiều nghiệm khi xét riêng toàn bộ clue. |
| §4.5 Thực nghiệm | 10 | Có puzzle cả ba kích thước và thống kê từng lần gọi DPLL. Chưa có kết quả thực nghiệm tổng hợp theo từng puzzle hoặc bảng so sánh trên cùng bộ dữ liệu. |
| §4.6 Báo cáo PDF | 30 | Chưa thấy báo cáo trong repo. Đề yêu cầu phân công và tỷ lệ hoàn thành, mô hình, dẫn xuất CNF, thuật toán, thực nghiệm, hạn chế, tài liệu tham khảo và phụ lục sử dụng AI. |
| §4.7 Video demo | 10 | Chưa thấy video hoặc liên kết trong repo. Đề yêu cầu khoảng 5–10 phút, trình diễn GUI, chơi tay và chạy bộ giải, có lời thuyết minh hoặc phụ đề tiếng Việt hay tiếng Anh. |
| **Tổng theo đề** | **100** | Xem trang 5–8 của [đề bài](<AI - Project 2.pdf>). |

Thực nghiệm cuối cùng cần ghi: số biến chính/phụ, số clause, số lần gọi SAT, số decisions/propagations/backtracks, số bước suy luận hoặc đợt mở thẻ, thời gian chạy. Kiểm thử hiện tại chưa thay thế thực nghiệm này. Các thuật toán chính phải do sinh viên tự cài đặt; thư viện hỗ trợ GUI/cấu trúc dữ liệu được phép dùng. Pure-literal elimination và heuristic phân nhánh nâng cao là tùy chọn.

## 3. Cấu trúc mã nguồn hiện tại

```text
Griductive/
├── AI - Project 2.pdf          # Đề bài học phần
├── AGENTS.md                  # Quy ước và phạm vi triển khai
├── README.md                  # Yêu cầu, cách chạy, cấu trúc và tiến độ
├── requirements.txt           # pygame-ce>=2.5,<3
├── main.py                    # CLI, danh sách màn, nạp puzzle, khởi tạo Engine và GUI
├── core/
│   ├── __init__.py
│   ├── models.py              # Dataclass, enum, protocol, đọc/kiểm tra JSON
│   ├── regions.py             # Tọa độ, vùng, ngữ nghĩa và mô tả/highlight clue
│   └── engine.py              # Trạng thái ván chơi, kiểm tra tay, ranh giới referee
├── gui/
│   ├── __init__.py
│   ├── app.py                 # GUI Pygame, danh sách màn, bàn chơi và điều khiển
│   └── avatars.py             # Vẽ chân dung nhân vật
├── solver/
│   ├── __init__.py
│   ├── dpll.py                # DPLL, mô hình SAT, timeout và thống kê
│   ├── encoder.py             # Mã hóa clue thành CNF và xây KB công khai
│   └── agent.py               # Phân loại, referee, Hint, trace và kiểm tra duy nhất
├── puzzles/
│   ├── *.json                 # 7 màn 3×3, 5 màn 4×4, 3 màn 5×5
│   └── SOURCES.txt            # Nguồn các màn hiện có
└── tests/
    ├── test_manual_game.py    # Engine, referee và bảo vệ dữ liệu
    ├── test_gui.py            # GUI headless và điều phối theo chế độ
    ├── test_level_selection.py # Chọn/đổi màn, phân trang và khởi động
    ├── test_solver_skeletons.py # Smoke test các kiểu kết quả và API
    ├── test_dpll.py           # DPLL và đối chiếu với vét cạn
    ├── test_encoder_agent.py  # Mã hóa CNF, Agent và các puzzle trong repo
    └── verify_puzzles.py      # Xác minh Step 1 cho các màn 3×3
```

### 3.1. Trách nhiệm và luồng dữ liệu

```text
puzzles/*.json -> tên file (chưa đọc nội dung) -> Chọn màn chơi -> Chơi
                                                               |
Puzzle JSON -> load_puzzle() -> Puzzle đã kiểm tra -> GameEngine
                                                     |
                                              get_public_state()
                                                     |
                                               PublicState -> GUI

GUI đọc engine.has_referee trước mỗi lần gửi kết luận:
  False -> submit_manual()  -> ManualResult
  True  -> submit_verdict() -> referee.judge(PublicState, ...) -> MoveResult
```

- `Puzzle`/`Cell` chứa dữ liệu đầy đủ, gồm đáp án và clue chưa mở. `GameEngine` giữ dữ liệu này.
- `PublicState` chỉ chứa `size`, `names`, `jobs` và trạng thái/clue của các thẻ đã mở. GUI và Agent dùng trạng thái công khai này.
- `submit_manual()` trả `CORRECT`, `WRONG` hoặc `ALREADY_REVEALED`; chỉ được dùng khi chưa có referee.
- `submit_verdict()` dành cho referee chứng minh logic. `ACCEPTED` mở thẻ; `NOT_PROVABLE` nghĩa là chưa buộc được trạng thái nào, `CONTRADICTED` nghĩa là trạng thái ngược lại được chứng minh. Các kết quả từ chối giữ nguyên bàn cờ. Engine còn kiểm tra kết luận được chấp nhận có khớp đáp án lưu sẵn trước khi mở thẻ.
- Gọi sai chế độ gây `RuntimeError`. Với thẻ đã mở, nhánh chứng minh trả `ALREADY_REVEALED` mà không gọi referee.
- `core` độc lập với `gui` và `solver`. Bộ giải chỉ import `core.models` và `core.regions` từ tầng core. Agent nhận `PublicState` và gửi kết luận qua `GameInterface`.

## 4. Cài đặt và chạy

Yêu cầu Python **3.10+**. Chạy các lệnh sau trong thư mục `Griductive` chứa `main.py`:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Ứng dụng mở màn hình **Chọn màn chơi** và tự liệt kê các file `.json` nằm trực tiếp trong thư mục `puzzles/` cạnh `main.py`. Tên màn là tên file bỏ đuôi `.json`, sắp xếp theo tên; không đọc hay kiểm tra nội dung file cho đến khi bấm **Chơi**. Thư mục con không được quét. Chọn một tên rồi bấm **Chơi** để bắt đầu; dùng **Trang trước/Trang sau**, cuộn chuột hoặc phím trái/phải (`Page Up`/`Page Down`) nếu có nhiều màn.

Thư mục puzzle được xác định từ vị trí `main.py`, nên chạy từ thư mục khác vẫn tìm đúng danh sách, ví dụ:

```powershell
python "C:\duong dan\Griductive\main.py"
```

Nếu `puzzles/` chưa tồn tại hoặc đang trống, màn hình hiển thị: **“Thêm file JSON vào thư mục puzzles/ hoặc chọn Mở file JSON”**. Có thể mở thẳng puzzle bằng tham số dòng lệnh:

```powershell
python main.py puzzles/3x3_01_easy.json
```

Hoặc truyền đường dẫn khác; đặt trong dấu ngoặc kép nếu đường dẫn có khoảng trắng:

```powershell
python main.py "C:\duong dan\puzzle.json"
```

Trên Windows có nhiều Python, dùng cùng một interpreter cho cả cài đặt và chạy, ví dụ `py -3.12 -m pip install -r requirements.txt` và `py -3.12 main.py`. Gói yêu cầu là `pygame-ce`, được import bằng tên `pygame`; `tkinter` thuộc bản phân phối Python có hỗ trợ Tk, không phải gói trong `requirements.txt`.

### Thao tác trong game

1. Trong **Chọn màn chơi**, chọn tên màn và bấm **Chơi** (hoặc `Enter`). Có thể nhấn **Mở file JSON** để chọn JSON ở bất kỳ thư mục nào. Bộ chọn file chạy trong tiến trình con. Nếu không mở được hộp thoại, nhập đường dẫn trong ứng dụng, nhấn `Enter` để nạp hoặc `Esc` để hủy.
2. Chọn một thẻ úp rồi nhấn **CRIMINAL** hoặc **INNOCENT**.
3. Đúng đáp án: mở đúng thẻ vừa chọn và hiện clue. Sai đáp án: báo `WRONG`, giữ thẻ úp và cho thử lại.
4. Chọn thẻ đã mở để highlight các ô liên quan; vùng chi tiết bên phải hiển thị clue được chọn, hữu ích trên bàn 5×5.
5. Nhấn **Restart** để khôi phục đúng tập thẻ mở ban đầu. Khi tất cả thẻ mở, game báo hoàn thành.
6. **Hint** và **Auto Solve** đang bị vô hiệu hóa trên GUI. Có thể gọi các chức năng tương ứng qua API ở mục 6.
7. Trong ván, nhấn **Chọn màn** để trở lại danh sách và quét lại thư mục, nhận các file mới. Chọn màn khác và bấm **Chơi** để bắt đầu ván mới. **Tiếp tục ván** quay về ván đang giữ trong bộ nhớ. **Restart** luôn khôi phục đúng các thẻ `revealed` của màn đã nạp thành công gần nhất.

Hủy nạp hoặc nạp file lỗi/đã bị xóa giữ nguyên ván đang chơi. Thông báo lỗi nêu tên file; bạn có thể chọn màn khác hoặc **Tiếp tục ván**. Chỉ thay bàn sau khi loader kiểm tra thành công toàn bộ file. Đường dẫn JSON hợp lệ trên dòng lệnh bỏ qua màn hình chọn màn; đường dẫn lỗi trở về màn hình chọn màn kèm thông báo. Game chỉ đọc puzzle, không sinh màn hoặc lưu đè tiến trình vào JSON. Các test dùng puzzle mẫu hiện tại cần giữ file mẫu đó.

## 5. Hợp đồng dữ liệu puzzle JSON

Puzzle chứa đúng hai trường gốc: `size` và `cells`. `size` là `3`, `4` hoặc `5`; `cells` có đúng `size * size` bản ghi, mỗi tọa độ xuất hiện đúng một lần.

Dưới đây là **một bản ghi ô trong mảng `cells`**, không phải puzzle hoàn chỉnh:

```json
{
  "id": "A1",
  "name": "Abel",
  "job": "Astronaut",
  "status": "INNOCENT",
  "revealed": true,
  "clue": {
    "id": "clue_A1",
    "type": "FACT",
    "cell": "B1",
    "status": "CRIMINAL"
  }
}
```

### 5.1. Các loại clue

Mọi clue có `id` duy nhất và trường `type`.

| `type` | Trường bổ sung | Ý nghĩa |
| --- | --- | --- |
| `FACT` | `cell`, `status` | Ô được chỉ định có trạng thái đã nêu |
| `SAME` | `cells: [cellA, cellB]` | Hai ô khác nhau có cùng trạng thái |
| `DIFFERENT` | `cells: [cellA, cellB]` | Hai ô khác nhau có trạng thái khác nhau |
| `EXACTLY` | `region`, `k` | Đúng `k` tội phạm trong vùng |
| `AT_LEAST` | `region`, `k` | Ít nhất `k` tội phạm trong vùng |
| `AT_MOST` | `region`, `k` | Nhiều nhất `k` tội phạm trong vùng |
| `PARITY` | `region`, `parity` | Số tội phạm chẵn (`EVEN`) hoặc lẻ (`ODD`) |
| `COMPARE` | `left`, `right`, `op` | So sánh số tội phạm hai vùng; toán tử `>`, `>=`, `=`, `<=`, `<` |

### 5.2. Các loại vùng

| Loại vùng | Ví dụ JSON | Ý nghĩa |
| --- | --- | --- |
| `ROW` | `{"type":"ROW","index":2}` | Toàn bộ hàng 2 |
| `COL` | `{"type":"COL","col":"B"}` | Toàn bộ cột B |
| `NEIGHBORS` | `{"type":"NEIGHBORS","of":"B2"}` | Các ô kề ngang, dọc, chéo; loại ô trung tâm |
| `EXPLICIT` | `{"type":"EXPLICIT","cells":["A1","C3"]}` | Danh sách các ô không trùng |
| `BOUNDARY` | `{"type":"BOUNDARY"}` | Các ô trên biên bàn cờ |
| `INTERSECTION` | `{"type":"INTERSECTION","of":[{"type":"ROW","index":2},{"type":"COL","col":"B"}]}` | Giao của ít nhất hai vùng; ví dụ này chỉ chứa B2 |

### 5.3. Chuẩn bị một bàn hoàn chỉnh

1. Tham khảo [puzzles/3x3_01_easy.json](puzzles/3x3_01_easy.json), có 9 ô và hai thẻ mở ban đầu `A1`, `B3`.
2. Chọn kích thước; khai báo đủ 9, 16 hoặc 25 ô. Ví dụ 3×3 phải có `A1, B1, C1, A2, B2, C2, A3, B3, C3`.
3. Mỗi ô phải có đủ `id`, `name`, `job`, `status`, `revealed`, `clue`; tên/nghề là chuỗi không rỗng, `revealed` là Boolean, trạng thái chỉ là `CRIMINAL` hoặc `INNOCENT`.
4. Đặt ID ô và ID clue không trùng; mọi tọa độ và vùng phải nằm trong bàn. Với clue đếm, `k` là số nguyên từ `0` đến số ô trong vùng.
5. Viết clue đúng dưới toàn bộ đáp án đã khai báo; chọn tập thẻ mở ban đầu phù hợp để suy luận. Theo đề, chuẩn bị tên nhân vật theo thứ tự bảng chữ cái; loader hiện chuẩn hóa theo tọa độ, không kiểm tra thứ tự tên.
6. Lưu JSON UTF-8 vào `puzzles/`, quay lại **Chọn màn** để cập nhật danh sách; hoặc dùng **Mở file JSON** hay tham số dòng lệnh. Loader từ chối trường thiếu/thừa, sai kiểu, tọa độ không hợp lệ, ID trùng và clue sai theo đáp án.

Loader dùng `evaluate_clue_directly()` để kiểm tra từng clue trên **một đáp án được cung cấp**, không liệt kê mọi phép gán. Nạp thành công chưa chứng minh puzzle có nghiệm duy nhất hoặc giải được từng bước không đoán.

## 6. Bộ giải và tích hợp

- Encoder đánh số biến chính từ 1 theo thứ tự hàng, `True` biểu thị `CRIMINAL`. `encode_clue()` dùng bộ đếm ngưỡng, cổng XOR và biến phụ mới. Khi ghép nhiều clue, dùng cùng một `Encoder` để các biến phụ có ID riêng. `build_kb()` mã hóa clue và trạng thái của các thẻ đã mở. [solver/encoder.py](solver/encoder.py)
- `solve(clauses, num_vars, assumptions=(), deadline=None)` chạy DPLL. `SolveResult` trả mô hình khi SAT, cờ timeout và số lần quyết định, lan truyền, quay lui cùng thời gian chạy. [solver/dpll.py](solver/dpll.py)
- Agent có `classify()`, `classify_all()`, `judge()`, `hint()`, `next_forced()`, `step()`, `run()` và `check_uniqueness()`. Agent chọn ô theo thứ tự hàng. `TraceStep` ghi bước, các ID clue đang hoạt động, truy vấn SAT dùng để tìm nước đi, kết luận và ID clue mới. Referee kiểm tra lại nước đi khi gửi vào Engine, vì vậy đếm truy vấn trong trace sẽ bỏ sót các lời gọi SAT ở lần kiểm tra này. [solver/agent.py](solver/agent.py)
- `hint()` trả ô có thể chứng minh và trạng thái của ô, với `relevant_clue_id` hiện là `None`. `run()` trả danh sách bước đã được chấp nhận và dừng khi hoàn thành, hết nước có thể chứng minh, gặp tri thức mâu thuẫn, timeout hoặc nước đi bị từ chối. API hiện trả trace mà chưa kèm mã lý do dừng.
- `check_uniqueness()` xét toàn bộ clue và chặn phép gán các biến chính sau nghiệm đầu tiên. Hai phép gán chỉ khác ở biến phụ vẫn biểu diễn cùng một lời giải.

Điểm tích hợp referee nằm trong `create_app()`, hiện khởi tạo `GameEngine(puzzle=None, referee=None)`. GUI đã đọc `has_referee` để điều phối thao tác gửi kết luận. [main.py](main.py)

Có thể chạy thử chế độ chứng minh bằng đoạn Python dưới đây từ thư mục gốc.

```python
from time import monotonic
from core.engine import GameEngine
from core.models import load_puzzle
from solver.agent import LogicAgent, check_uniqueness

puzzle = load_puzzle("puzzles/3x3_01_easy.json")
agent = LogicAgent(deadline=monotonic() + 20)
game = GameEngine(puzzle, referee=agent)
trace = agent.run(game)
result = check_uniqueness(
    puzzle.size, [card.clue for card in puzzle.cells], deadline=monotonic() + 20
)
print(game.is_solved(), len(trace), result.status.value)  # True 7 UNIQUE
```

Deadline là mốc tuyệt đối từ `time.monotonic()` dùng chung cho các lần gọi SAT trong một lượt giải. Mã hóa chạy trước các kiểm tra deadline trong DPLL. Số thứ tự bước tăng theo vòng đời của một `LogicAgent`.

### Đối chiếu với mốc thủ công trong AGENTS.md

- Đã có danh sách tên màn sắp xếp, nạp và kiểm tra khi bấm chơi, quét lại khi mở danh sách, giữ tiến độ khi nạp lỗi, tiếp tục ván và tham số mở JSON trực tiếp. Khởi động thiếu thư mục hoặc chưa có JSON vẫn vào được màn chọn.
- AGENTS.md yêu cầu bấm tên màn để chơi ngay. Hiện cần bấm thêm **Chơi** hoặc `Enter`. Khi thư mục trống, giao diện hiện **“Thêm file JSON vào thư mục puzzles/ hoặc chọn Mở file JSON”**. Câu yêu cầu là **“Chưa có màn chơi. Hãy thêm file JSON vào thư mục puzzles/.”**
- Chơi thủ công và chơi có referee trả hai kiểu kết quả riêng. GUI luyện tập giải thích vì sao Hint và Auto Solve bị tắt. Chế độ chứng minh hiện có thêm bước kiểm tra nhất quán với lời giải lưu sẵn trong Engine sau khi referee trả `ACCEPTED`.

## 7. Kiểm thử và kết quả kiểm chứng

Chạy từ thư mục gốc `Griductive`. Trên Windows, các lệnh dưới đây dùng Python 3.12. Có thể thay `py -3.12` bằng `python` trỏ tới cùng môi trường.

```powershell
py -3.12 -B -m unittest discover -s tests -v
py -3.12 -B -m unittest tests.test_dpll tests.test_encoder_agent tests.test_solver_skeletons
py -3.12 -B -m tests.verify_puzzles
py -3.12 -B main.py --help
```

### 7.1. Kết quả chạy ngày 26/11/2026

Đã chạy trên Windows với Python 3.12.10 và gói `pygame` 2.6.0 có sẵn. Bản cài mới theo `requirements.txt` (`pygame-ce`) chưa được kiểm tra trong lần rà soát này.

| Lệnh | Kết quả |
| --- | --- |
| `py -3.12 -B -m unittest discover -s tests -v` | **27/38 đạt** ngoài sandbox. 10 lỗi đọc puzzle và 1 assertion lỗi trong test CLI đều do các test còn tham chiếu tên cũ `3x3_easy.json` hoặc `3x3_easy`. |
| `py -3.12 -B -m unittest tests.test_dpll tests.test_encoder_agent tests.test_solver_skeletons` | **18/18 đạt**. Có kiểm tra SAT/UNSAT/timeout, đối chiếu CNF với evaluator, phân loại, trace và tự giải tất cả puzzle trong repo. |
| `py -3.12 -B -m tests.verify_puzzles` | **4/4 đạt**. Verifier Step 1 nạp và kiểm tra JSON, rồi vét cạn nghiệm và mô phỏng suy luận riêng cho 7 màn 3×3. |
| `py -3.12 -B main.py --help` | Hiển thị tham số tùy chọn `puzzle`. |

Các tham chiếu cũ làm lỗi 4 test GUI, 6 test Engine và 1 test CLI. Lượt chạy trong sandbox còn gặp lỗi quyền truy cập thư mục fixture tạm.

### 7.2. Kiểm tra bộ puzzle

| Kích thước | Nạp hợp lệ | Giải không đoán từ thẻ mở sẵn | Nghiệm duy nhất khi chỉ xét toàn bộ clue |
| --- | ---: | ---: | ---: |
| 3×3 | 7/7 | 7/7 | 7/7 |
| 4×4 | 5/5 | 5/5 | 4/5 |
| 5×5 | 3/3 | 3/3 | 2/3 |
| **Tổng** | **15/15** | **15/15** | **13/15** |

Đã gọi `LogicAgent.run()` và `check_uniqueness()` riêng cho từng file như ví dụ ở mục 6. Hai ngoại lệ là [4x4_04_medium.json](puzzles/4x4_04_medium.json) và [5x5_03_hard.json](puzzles/5x5_03_hard.json). Với mỗi file, evaluator trực tiếp xác nhận hai phép gán khác nhau đều thỏa toàn bộ clue. Thêm trạng thái các thẻ mở sẵn dưới dạng `FACT` cho kết quả duy nhất, khớp đáp án lưu. Hai màn vì vậy giải được từ bàn ban đầu nhưng chưa đạt kiểm tra duy nhất chỉ với toàn bộ clue theo §4.4.

Tên hiển thị của các nhân vật trong cả 15 bàn đã theo thứ tự bảng chữ cái khi duyệt theo hàng và bỏ qua hoa/thường. Loader chuẩn hóa theo tọa độ. Khi thêm màn, thứ tự tên vẫn do người soạn dữ liệu quyết định. Nguồn của các màn được ghi trong [puzzles/SOURCES.txt](puzzles/SOURCES.txt).

### 7.3. Phạm vi kiểm tra GUI

- **File thật, SDL dummy và sự kiện tổng hợp.** Đã mở selector từ thư mục cha và kiểm tra đủ 15 tên sắp xếp trước khi chọn. Đã chọn màn thứ hai `3x3_02_easy`, gửi sai rồi đúng, chọn lặp lại thẻ đã mở và kiểm tra highlight. Đã kiểm tra nút Hint/Auto Solve bị khóa, nạp đường dẫn lỗi rồi tiếp tục ván, Restart, chuyển sang `3x3_01_easy`, hoàn thành và quay lại danh sách. Đã mở thẳng `5x5_03_hard` qua tham số CLI và kiểm tra CLI trở về selector khi đường dẫn sai.
- **Referee thật, SDL dummy.** Dùng `3x3_02_easy` với Agent inject trực tiếp vào Engine. GUI trả `NOT_PROVABLE` cho lựa chọn đúng nhưng chưa chứng minh được, `CONTRADICTED` khi chứng minh được trạng thái ngược lại và `ACCEPTED` khi kết luận được chứng minh. Chỉ trường hợp cuối mở thẻ.
- **Fixture.** Các test đạt đã kiểm tra thư mục trống/thiếu, quét lại khi có file mới, JSON lỗi/đã xóa vẫn giữ ván, phân trang qua 30 tên, chuyển giữa fixture 3×3 và 4×4, nạp ngoài danh sách và nhập đường dẫn dự phòng với hộp thoại giả lập. Fixture trong bộ nhớ dùng để vẽ đủ ba kích thước.
- **Ranh giới dữ liệu.** Lượt kiểm tra chơi tay với file thật chạy trong tiến trình Python mới. Sau các nước đi, `sys.modules` không có `solver` hoặc `solver.*`, và SHA-256 của cả 15 file JSON giữ nguyên.
- **Phạm vi trực quan.** Lần rà soát này dùng driver SDL dummy. Cửa sổ tương tác, hộp thoại chọn file của hệ điều hành và độ dễ đọc của clue dài khi cuộn chưa được kiểm chứng trực tiếp.

## 8. Quy cách bài nộp và việc còn lại

Theo trang 8–9 của đề, cấu trúc nộp tham khảo:

```text
StudentID1_StudentID2_.../
├── Source/
│   ├── main.py
│   ├── README.md
│   ├── requirements.txt
│   └── ...
└── Report.pdf                 # Có liên kết video demo
```

- Đóng gói `.zip` hoặc `.rar`, đặt tên theo mã số thành viên. Nếu lớn hơn 20 MB, tải lên Google Drive và chia sẻ liên kết; không sửa sau hạn nộp.
- Báo cáo cần dẫn xuất CNF cho ít nhất một clue nhị phân và một clue đếm; mô tả DPLL, phân loại bằng entailment, kiểm tra duy nhất và vòng lặp suy luận.
- Ghi phân công, tỷ lệ hoàn thành từng thành viên và cách dùng AI/prompts trong phụ lục theo yêu cầu. README hiện chưa có dữ liệu để điền thông tin này.
- Video dùng Google Drive, cho phép bất kỳ ai có liên kết xem được; kiểm tra bằng cửa sổ riêng tư/ẩn danh. Không nộp liên kết YouTube.
- Đề nêu thời lượng khoảng ba tuần nhưng không ghi ngày hết hạn cụ thể; cần đối chiếu thông báo học phần.

Các việc còn lại trước khi nộp gồm nối chế độ chứng minh, Hint và Auto Solve vào GUI, cập nhật tên fixture trong các test, và rà soát hai puzzle có nhiều nghiệm khi xét riêng toàn bộ clue. Thực nghiệm cần tổng hợp số biến chính/phụ, số mệnh đề, tổng số lần gọi SAT, decisions/propagations/backtracks, số bước suy luận và thời gian. Dùng cùng bộ puzzle cho các phương án so sánh và ghi nhận trường hợp thất bại hoặc timeout. Báo cáo và video cần dựa trên ứng dụng đã tích hợp và kết quả thực nghiệm.
