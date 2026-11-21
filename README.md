# Griductive Solver — CSC14003, Project 2

Đồ án **Nhập môn Trí tuệ nhân tạo**: xây dựng trò chơi Griductive và bộ giải suy luận bằng logic mệnh đề, mã hóa CNF và thuật toán DPLL tự cài đặt.

**Cập nhật tiến độ: 21/11/2026.** Phiên bản hiện tại đã có game luyện tập thủ công bằng Pygame, bộ đọc/kiểm tra puzzle JSON và các giao diện dành cho bộ giải. Phần mã hóa CNF, DPLL và suy luận tự động chưa được triển khai.

> Chế độ đang chạy là **Manual practice — answer check**: so sánh lựa chọn với đáp án lưu trong puzzle. Đoán đúng vẫn được lật thẻ; trả lời sai cũng có thể giúp suy ra trạng thái còn lại. Vì vậy, chế độ này **chưa đáp ứng yêu cầu không đoán (no-guess)** của đề và chưa hoàn thành toàn bộ phần game được chấm điểm.

## 1. Tài liệu và phạm vi

- [AI - Project 2.pdf](<AI - Project 2.pdf>): yêu cầu học phần, tiêu chí đánh giá và quy cách nộp bài.
- [AGENTS.md](AGENTS.md): quy ước phát triển hiện tại; giới hạn phần triển khai ở game luyện tập và giữ thuật toán tự động cho sinh viên thực hiện.
- README này đối chiếu hai tài liệu trên với mã nguồn và kết quả kiểm thử hiện có. Trạng thái “đã có” không đồng nghĩa với việc hoàn thành tiêu chí chấm điểm tương ứng.

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

Kiểm tra KB_t trước: UNSAT => INCONSISTENT
KB_t AND NOT C_i là UNSAT => CRIMINAL
KB_t AND C_i là UNSAT     => INNOCENT
Cả hai phép thử đều SAT   => UNKNOWN
```

### 2.2. Các hạng mục được đánh giá

| Hạng mục | Điểm | Yêu cầu chính |
| --- | ---: | --- |
| Game có GUI | 10 | Bàn cờ, gọi trạng thái, kiểm tra bằng chứng, lật thẻ, highlight clue; Load, Restart, Hint, Auto Solve; tách Engine và Agent |
| Biểu diễn logic và CNF | 10 | Ánh xạ biến xác định, kiểm tra clue/vùng, tự mã hóa clue, thêm unit clause, thống kê biến/mệnh đề, có evaluator ngữ nghĩa trực tiếp |
| DPLL tự cài đặt | 10 | Unit propagation, phát hiện xung đột, chọn biến xác định, phân nhánh/đệ quy/quay lui, trả SAT kèm phép gán đầy đủ hoặc UNSAT; thống kê tìm kiếm |
| Logic Agent | 20 | Phân loại ô chưa mở, chỉ chọn kết luận bắt buộc, cập nhật KB, trace suy luận, Hint và kiểm tra nghiệm duy nhất riêng |
| Thực nghiệm | 10 | Nhiều puzzle 3×3 và 4×4; có thể thêm 5×5; cùng tập dữ liệu khi so sánh; công bố cả thất bại và timeout |
| Báo cáo PDF | 30 | Phân công và tỷ lệ hoàn thành từng thành viên, mô hình bài toán, dẫn xuất CNF, thuật toán, thực nghiệm, hạn chế, tài liệu tham khảo và phụ lục sử dụng AI |
| Video demo | 10 | Khoảng 5–10 phút, trình diễn GUI, chơi tay và bộ giải; thuyết minh/phụ đề tiếng Việt hoặc tiếng Anh |
| **Tổng** | **100** | Chi tiết tại trang 5–8 của đề |

Ngoài sáu loại clue cốt lõi, mỗi nhóm phải triển khai **ít nhất hai mở rộng khác nhau**. Hiện mã nguồn có ngữ nghĩa cho `PARITY`, `COMPARE`, `BOUNDARY`, `INTERSECTION`, nhưng chưa có mã hóa CNF và kiểm thử tích hợp bộ giải cho các mở rộng này.

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
│   └── app.py                 # GUI Pygame, chọn file/nhập đường dẫn, sự kiện
├── solver/
│   ├── __init__.py
│   ├── dpll.py                # Kiểu kết quả và khung solve(), chưa có thuật toán
│   ├── encoder.py             # Ánh xạ biến đã có; mã hóa/KB còn là khung
│   └── agent.py               # Kiểu kết quả và khung LogicAgent/uniqueness
├── puzzles/
│   └── 3x3_easy.json           # Puzzle hoàn chỉnh hiện có
├── tests/
│   ├── __init__.py
│   ├── test_manual_game.py    # 6 test Engine, referee, bảo vệ dữ liệu
│   ├── test_gui.py            # 7 test GUI headless và điều phối theo chế độ
│   ├── test_level_selection.py # 7 test chọn/đổi màn, phân trang và khởi động
│   ├── test_solver_skeletons.py # 3 test import/khung giao diện
│   └── verify_puzzles.py      # 4 test xác minh Step 1, chạy riêng khi cần
└── generate_puzzles.py        # Tệp di sản Step 1, không dùng trong luồng hiện tại
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
- `core` độc lập với `gui` và `solver`. Bộ giải tương lai chỉ dùng `core.models` và `core.regions` từ tầng core; không truy cập dữ liệu riêng của Engine.

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
python main.py puzzles/3x3_easy.json
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
6. **Hint** và **Auto Solve** đang bị vô hiệu hóa, chờ triển khai và kết nối Agent.
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

1. Tham khảo [puzzles/3x3_easy.json](puzzles/3x3_easy.json), hiện có 9 ô và hai thẻ mở ban đầu `A1`, `B3`.
2. Chọn kích thước; khai báo đủ 9, 16 hoặc 25 ô. Ví dụ 3×3 phải có `A1, B1, C1, A2, B2, C2, A3, B3, C3`.
3. Mỗi ô phải có đủ `id`, `name`, `job`, `status`, `revealed`, `clue`; tên/nghề là chuỗi không rỗng, `revealed` là Boolean, trạng thái chỉ là `CRIMINAL` hoặc `INNOCENT`.
4. Đặt ID ô và ID clue không trùng; mọi tọa độ và vùng phải nằm trong bàn. Với clue đếm, `k` là số nguyên từ `0` đến số ô trong vùng.
5. Viết clue đúng dưới toàn bộ đáp án đã khai báo; chọn tập thẻ mở ban đầu phù hợp để suy luận. Theo đề, chuẩn bị tên nhân vật theo thứ tự bảng chữ cái; loader hiện chuẩn hóa theo tọa độ, không kiểm tra thứ tự tên.
6. Lưu JSON UTF-8 vào `puzzles/`, quay lại **Chọn màn** để cập nhật danh sách; hoặc dùng **Mở file JSON** hay tham số dòng lệnh. Loader từ chối trường thiếu/thừa, sai kiểu, tọa độ không hợp lệ, ID trùng và clue sai theo đáp án.

Loader dùng `evaluate_clue_directly()` để kiểm tra từng clue trên **một đáp án được cung cấp**, không liệt kê mọi phép gán. Nạp thành công chưa chứng minh puzzle có nghiệm duy nhất hoặc giải được từng bước không đoán.

## 6. Tiến độ hiện tại

| Thành phần | Trạng thái từ mã nguồn/kiểm thử |
| --- | --- |
| Mô hình dữ liệu, enum và protocol | Đã có `Puzzle`, `Cell`, `Clue`, `Region`, `PublicState`, `GameInterface`, `Referee`, các kiểu verdict/kết quả |
| Đọc và kiểm tra JSON | Đã có cho 3×3, 4×4, 5×5; kiểm tra cấu trúc, tham chiếu và tính đúng của clue theo đáp án |
| Ngữ nghĩa clue/vùng | Đã có evaluator trực tiếp cho 6 clue cốt lõi, `PARITY`, `COMPARE`; hỗ trợ thêm biên và giao vùng |
| Engine chơi thủ công | Đã có nạp, trả lời đúng/sai, từ chối ô đã mở, Restart, phát hiện hoàn thành và trạng thái công khai |
| GUI luyện tập | Đã có bàn cờ, Load, chọn trạng thái, highlight, thông báo và vùng chi tiết clue; đã kiểm thử headless |
| Ranh giới referee | Đã có inject và điều phối theo `has_referee`; test bằng referee giả lập, chưa có referee suy luận thật |
| Ánh xạ biến | `Encoder.var_of()`/`cell_of()` hoạt động, đánh số từ 1 theo hàng; chưa mã hóa clue |
| CNF và KB | `encode_clue()` và `build_kb()` còn `NotImplementedError` |
| DPLL | Có kiểu kết quả/thống kê và chữ ký `solve()`; thân thuật toán còn `NotImplementedError` |
| Logic Agent, Hint, Auto Solve | Có khung API và kiểu trace/hint; chưa có suy luận hoặc chạy giải tự động |
| Kiểm tra nghiệm duy nhất | API chính thức `check_uniqueness()` chưa triển khai; chỉ có verifier vét cạn 3×3 riêng của Step 1 |
| Bộ puzzle | Có một file 3×3 hoàn chỉnh; chưa có file 4×4/5×5 trong `puzzles/` |
| Thực nghiệm và thống kê bộ giải | Chưa có bộ thực nghiệm/bảng kết quả trong cấu trúc hiện tại |
| Báo cáo, phân công, video demo | Chưa thấy báo cáo PDF, bảng phân công hoặc liên kết video trong các tệp hiện tại |

### Phần sinh viên cần triển khai tiếp

- **`solver/encoder.py`**: `Encoder.encode_clue(clue)` và `build_kb(state)`; chuyển clue công khai thành CNF, thêm unit clause, quản lý biến phụ và thống kê. `KnowledgeBase` và `EncoderStatistics` đã có.
- **`solver/dpll.py`**: `solve(clauses, num_vars, assumptions=(), deadline=None) -> SolveResult`; bổ sung DPLL, model đầy đủ, timeout và `SolveStatistics`.
- **`solver/agent.py`**: `LogicAgent.classify`, `judge`, `hint`, `next_forced`, `classify_all`, `step`, `run` và hàm `check_uniqueness(size, clues)`. Các kiểu `Hint`, `SatQuery`, `TraceStep`, `UniquenessResult` đã có.
- **Tích hợp GUI**: sau khi Agent hoạt động, nối Hint/Auto Solve, cập nhật hiển thị theo chế độ, trace và các trạng thái kết thúc.
- **Hoàn thiện bài nộp**: bổ sung puzzle do người dùng chuẩn bị cho thực nghiệm, kiểm thử thuật toán, đo thống kê, viết báo cáo và quay video.

Điểm tích hợp referee nằm trong `create_app()` của `main.py`, hiện là `GameEngine(puzzle=None, referee=None)`. Khi `LogicAgent.judge()` hoàn thiện, có thể inject như sau:

```python
from solver.agent import LogicAgent

engine = GameEngine(puzzle=None, referee=LogicAgent())
```

Đây là hướng tích hợp tương lai; thay đổi này hiện sẽ gọi các hàm chưa được triển khai. GUI đã chọn đúng nhánh `submit_verdict()` khi có referee, nhưng hai nút Hint/Auto Solve vẫn cần được nối riêng.

## 7. Kiểm thử và kết quả kiểm chứng

Chạy từ thư mục gốc `Griductive`:

```powershell
python -m unittest discover -s tests -v
```

Lệnh trên chạy 23 test trong các tệp `test_*.py`. Các test GUI tự đặt `SDL_VIDEODRIVER=dummy`, không mở cửa sổ tương tác. Trong đó, 7 test mới ở `test_level_selection.py` dùng file JSON fixture tạm để kiểm tra chọn màn thứ hai rồi quay lại màn thứ nhất, Restart, quét lại, thư mục trống/thiếu, file lỗi/đã xóa, duyệt 30 màn qua các trang, mở file ngoài danh sách và CLI từ thư mục khác. Fixture được dọn sau test, không ghi vào `puzzles/` thật.

Verifier Step 1 là lệnh tùy chọn, chạy riêng:

```powershell
python -m tests.verify_puzzles
```

Verifier này vét cạn các phép gán 3×3 để kiểm tra clue, nghiệm duy nhất và khả năng mở thẻ không đoán. Nó **không phải DPLL hoặc Agent cần nộp**. Hiện verifier yêu cầu có puzzle và chỉ chấp nhận file 3×3 trong `puzzles/`; không dùng nguyên trạng cho thư mục có puzzle 4×4/5×5.

### 7.1. Kết quả chạy ngày 21/11/2026

Môi trường kiểm chứng: Windows, Python **3.12.10**, module Pygame **2.6.0** đang cài sẵn. Dependency khai báo vẫn là `pygame-ce>=2.5,<3`; lần rà soát này không xác nhận một lượt cài mới dependency trên môi trường sạch.

| Lệnh thực tế | Kết quả |
| --- | --- |
| `py -3.12 -B -m unittest discover -s tests -v` | **23/23 đạt**: 6 Engine + 7 GUI + 7 chọn màn + 3 khung solver |
| `py -3.12 -B -m tests.verify_puzzles` | **4/4 đạt** với dữ liệu hiện có |
| `py -3.12 -B -m core.engine` | Thành công, kiểm tra khởi tạo Engine với puzzle mẫu |
| `py -3.12 -B -m solver.dpll` | Thành công, smoke test kiểu dữ liệu và khung `solve()` |
| `py -3.12 -B -m solver.encoder` | Thành công, smoke test ánh xạ biến |
| `py -3.12 -B -m solver.agent` | Thành công, smoke test kiểu dữ liệu và khung Agent |
| `py -3.12 -B main.py --help` | Thành công, hiển thị tham số puzzle tùy chọn |

Sandbox Windows chặn quyền truy cập thư mục fixture tạm. Chạy lại bộ 23 test ngoài sandbox đạt toàn bộ. Các smoke test solver chỉ xác nhận giao diện import được và hành vi khung đúng dự kiến, **không chứng minh thuật toán hoạt động**.

### 7.2. Phạm vi đã kiểm chứng

- **Với file thật `puzzles/3x3_easy.json`**: nạp bằng loader; Engine trả lời sai/đúng, gửi lại ô đã mở, Restart và mở hết bàn; GUI headless điều phối sai rồi đúng, chọn lặp lại, highlight clue và nhánh referee giả lập.
- **Với file JSON hỏng tạm thời**: GUI gọi loader thật giữa ván và giữ nguyên trạng thái khi nạp lỗi.
- **Với file fixture tạm và loader thật**: chọn màn thứ hai 4×4, quay lại màn thứ nhất 3×3 và Restart; thư mục trống/thiếu; JSON hỏng, sai schema và file bị xóa cạnh file hợp lệ; quét lại thấy file mới; phân trang qua 30 tên; mở file ngoài danh sách, hủy và nhập đường dẫn dự phòng. Test CLI chạy từ thư mục khác xác nhận tìm đúng `puzzles/` cạnh `main.py`, mở thẳng file hợp lệ và hiển thị lỗi khi đường dẫn sai.
- **Ảnh render headless**: đã kiểm tra bố cục màn chọn với puzzle thật `3x3_easy.json`, trạng thái thư mục trống và bàn chơi; font ưu tiên Tahoma/DejaVu Sans để hiển thị tiếng Việt. Đây là kiểm tra ảnh render, không phải thao tác trực tiếp với cửa sổ hệ điều hành.
- **Với fixture trong bộ nhớ/callback giả lập**: màn hình trống; nạp bàn thứ hai, hủy/đường dẫn lỗi; vẽ bàn 3×3, 4×4, 5×5, nhận click tổng hợp và chạy một frame. Chưa có file puzzle thật 4×4/5×5 để kiểm chứng nạp đầu cuối.
- **Ranh giới dữ liệu**: test dùng tiến trình Python mới xác nhận sau một nước chơi thủ công không có `solver`/`solver.*` trong `sys.modules`; hash puzzle không đổi. Referee giả lập kiểm tra từ chối, timeout/lỗi, gọi sai chế độ và thẻ đã mở không gọi `judge()`.
- **Chưa kiểm chứng trực quan trong lần rà soát này**: cửa sổ GUI thật, hộp thoại chọn file của hệ điều hành, nhập đường dẫn qua bàn phím, khả năng đọc đủ clue rất dài trên màn hình nhỏ. Code hiện ngắt vẽ chi tiết khi hết chiều cao panel; cần kiểm tra thêm với clue dài.

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

Ưu tiên tiếp theo là hoàn thiện CNF và DPLL, xây Agent chứng minh từng nước đi, tích hợp GUI, rồi thực nghiệm trên nhiều puzzle 3×3/4×4 để có dữ liệu cho báo cáo và video.
