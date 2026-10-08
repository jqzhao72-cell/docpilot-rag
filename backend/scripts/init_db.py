"""Create/upgrade the application database, backing up existing data first."""
from app.database import engine
from app.migrations import upgrade

if __name__ == "__main__":
    upgrade(engine)
    print("数据库初始化/迁移完成；原数据库备份位于 backend/backups（如适用）。")
