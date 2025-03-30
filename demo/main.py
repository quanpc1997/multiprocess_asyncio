from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from database import get_db, engine, AsyncSessionLocal
import models
from models import User
import aiohttp
import asyncio
import time
import multiprocessing
import concurrent.futures
from functools import partial
import os
from datetime import datetime

app = FastAPI()
total_requests = 1000000
batch_size = 10000

# Pydantic models
class UserBase(BaseModel):
    email: str
    name: str
    password: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Create tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

async def fetch_data(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

async def save_users_batch(db: AsyncSession, start_idx: int, batch_size: int):
    try:
        users = []
        current_time = datetime.utcnow()
        for i in range(start_idx, start_idx + batch_size):
            users.append(User(
                email=f"user{i}@example.com",
                name=f"user{i}",
                password=f"password{i}",
                created_at=current_time
            ))
        db.add_all(users)
        await db.commit()
        return len(users)
    except Exception as e:
        print(f"Error saving batch: {e}")
        await db.rollback()
        return 0

async def process_batch(start_idx: int, end_idx: int, url: str, db: AsyncSession):
    successful_saves = 0  # Kích thước batch cho việc lưu users
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(start_idx, end_idx):
            tasks.append(fetch_data(session, url))
        
        results = await asyncio.gather(*tasks)
        
        # Lưu users theo batch
        for i in range(start_idx, end_idx, batch_size):
            batch_end = min(i + batch_size, end_idx)
            if await save_users_batch(db, i, batch_end - i):
                successful_saves += (batch_end - i)
    
    return successful_saves

def run_async_process(start_idx: int, end_idx: int, url: str):
    async def main():
        async with AsyncSessionLocal() as db:
            return await process_batch(start_idx, end_idx, url, db)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(main())
    finally:
        loop.close()

@app.post("/fetch-and-save/")
async def fetch_and_save_users(db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    url = "http://localhost:8001/"  # URL của server1  # Số lượng request đồng thời
    successful_saves = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, total_requests, batch_size):
            tasks = []
            for _ in range(min(batch_size, total_requests - i)):
                tasks.append(fetch_data(session, url))
            
            results = await asyncio.gather(*tasks)
            
            # Lưu users theo batch
            batch_end = min(i + batch_size, total_requests)
            if await save_users_batch(db, i, batch_end - i):
                successful_saves += (batch_end - i)
            
            print(f"Đã xử lý {i + len(tasks)}/{total_requests} requests")
            print(f"Số bản ghi đã lưu thành công: {successful_saves}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    return {
        "message": "Hoàn thành xử lý",
        "total_requests": total_requests,
        "successful_saves": successful_saves,
        "duration_seconds": duration,
        "requests_per_second": total_requests / duration
    }

@app.post("/fetch-and-save-multiprocess/")
async def fetch_and_save_users_multiprocess(db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    url = "http://localhost:8001/"  # URL của server1  # Tổng số request cần thực hiện
    
    # Lấy số CPU cores
    num_cores = multiprocessing.cpu_count()
    print(f"Số CPU cores: {num_cores}")
    
    # Tính số request cho mỗi process
    requests_per_process = total_requests // num_cores
    print(f"Số request cho mỗi process: {requests_per_process}")
    
    # Tạo các ranges cho mỗi process
    process_ranges = []
    for i in range(num_cores):
        start_idx = i * requests_per_process
        end_idx = start_idx + requests_per_process if i < num_cores - 1 else total_requests
        process_ranges.append((start_idx, end_idx))
    
    # Chạy các process
    successful_saves = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_cores) as executor:
        # Tạo partial function với các tham số cố định
        process_func = partial(run_async_process, url=url)
        
        # Chạy các process và thu thập kết quả
        futures = [executor.submit(process_func, start, end) 
                  for start, end in process_ranges]
        
        # Theo dõi tiến trình
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            successful_saves += future.result()
            print(f"Process {completed}/{num_cores} hoàn thành")
            print(f"Tổng số bản ghi đã lưu: {successful_saves}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    return {
        "message": "Hoàn thành xử lý",
        "total_requests": total_requests,
        "successful_saves": successful_saves,
        "duration_seconds": duration,
        "requests_per_second": total_requests / duration,
        "num_processes": num_cores
    }

@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(
        email=user.email,
        name=user.name,
        password=user.password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=List[UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return users

@app.get("/users/{user_id}", response_model=UserResponse)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user




