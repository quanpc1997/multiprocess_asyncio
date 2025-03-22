# Multiprocess

## I. Concurrent
### Khởi tạo Process
Có nhiều cách khởi tạo Process nhưng tối ưu nhất là dùng gói concurrent.

```python
from concurrent.futures import ProcessPoolExecutor

if __name__ == "__main__":
    with ProcessPoolExecutor() as executor:
        pass
```

### Các phương thức hỗ trợ
#### 1. map()
Tham số truyền vào là callback tên hàm với tham số truyền vào nên là 1 args(1 tuple). 
```python
import concurrent.futures
import os
import time

def worker(args):
    (n, m, e) = args
    print(f"Tiến trình {os.getpid()} đang xử lý {n}")
    time.sleep(2)
    return n * n

if __name__ == "__main__":
    numbers = [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4), (5, 5, 5)]

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(worker, numbers)

    print("Kết quả:", list(results))
```
Hoặc nếu tham số không muốn truyền vào kiểu tuple thì ra sử dụng ```functools.partial```. Nhưng kiểu này sẽ khó hơn và không dễ như sử dụng args.

#### 2. submit()
Hàm ```executor.submit(fn, *args, **kwargs)``` gửi một tác vụ đến pool tiến trình và trả về một đối tượng Future.

Nói cách khác, nó không chạy ngay lập tức mà chỉ lên lịch chạy tác vụ đó trên một tiến trình khác. Bạn có thể sử dụng ```future.result()``` để lấy kết quả khi tiến trình hoàn thành.

```python
import concurrent.futures
import os

def worker(n):
    print(f"Tiến trình {os.getpid()} đang xử lý {n}")
    return n * n

if __name__ == "__main__":
    numbers = [1, 2, 3, 4, 5]
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(worker, num): num for num in numbers}

        for future in concurrent.futures.as_completed(futures):
            num = futures[future]
            try:
                result = future.result()
                print(f"Kết quả của {num}: {result}")
            except Exception as e:
                print(f"Lỗi khi xử lý {num}: {e}")
```
- ```concurrent.futures.as_completed(futures)```: Lặp qua các Future theo thứ tự hoàn thành (không phải theo thứ tự gửi).

## II. Kết hợp với asyncio.
```python
import concurrent.futures
import os
import asyncio
import time

async def get_data(args):
    (n, _) = args
    await asyncio.sleep(5)
    print(f"Async thứ {n}")
    return True

def worker(data):
    return asyncio.run(get_data(data))

if __name__ == "__main__":
    start_time = time.time()
    numbers = [(1, 9), (2, 8), (3, 7), (4, 6), (5, 5), (1, 9), (2, 8), (3, 7), (4, 6), (5, 5), (1, 9), (2, 8), (3, 7), (4, 6), (5, 5)]
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(worker, num): num for num in numbers}

        for future in concurrent.futures.as_completed(futures):
            num = futures[future]
            try:
                result = future.result()
                print(f"Kết quả của {num}: {result}")
            except Exception as e:
                print(f"Lỗi khi xử lý {num}: {e}")

    end_time = time.time()
    print(f"Thời gian phản hồi: {end_time-start_time}")
# Kết quả:
# Thời gian phản hồi: 10.294984102249146
```
B1: Tạo hàm async
```python
async def get_data(args):
    (n, _) = args
    asyncio.sleep(2)
    print(f"Async thứ {n}")
    return True
```
B2: Tạo hàm bọc để chạy hàm async
```python
def worker(data):
    return asyncio.run(get_data(data))
```
B3: Nạp hàm bọc để process chạy
```python
futures = {executor.submit(worker, num): num for num in numbers}
```
