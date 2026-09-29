from sqlalchemy import inspect

from app.database import engine


inspector = inspect(engine)

tables = inspector.get_table_names()

print("当前数据库中的表：")

for table in tables:
    print(table)