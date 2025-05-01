import sys
from pathlib import Path

# 添加项目根目录到Python路径，以便导入配置模块
project_root = Path(__file__).resolve().parents[1]  # 上移一级目录到项目根目录
sys.path.append(str(project_root))

# 然后再导入项目模块
from app.multi_agent.external_apis.twitter.get_latest_tweets import TwitterMonitor, TwitterConfig


def main():
    # 创建TwitterMonitor实例
    config = TwitterConfig()
    
        
    # 启动监控
    monitor = TwitterMonitor(config)
    monitor.start_monitoring()


# 添加这个条件判断，使得脚本被直接运行时会调用main函数
if __name__ == "__main__":
    main()




