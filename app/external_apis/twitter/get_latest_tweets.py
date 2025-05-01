import os
import time
import requests
import schedule
import json
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# 添加项目根目录到Python路径，以便导入配置模块
project_root = Path(__file__).resolve().parents[3]  # 上移三级目录到项目根目录
sys.path.append(str(project_root))

# 导入配置
from app.external_apis.twitter.config_tweets import TwitterConfig as ConfigClass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TwitterConfig:
    """Twitter API配置类"""
    
    def __init__(self):
        # 从配置类加载配置
        self.enabled = ConfigClass.ENABLED
        self.bearer_token = ConfigClass.BEARER_TOKEN
        self.target_users = ConfigClass.TARGET_USERS
        self.interval_minutes = ConfigClass.INTERVAL_MINUTES
        self.output_dir = ConfigClass.OUTPUT_DIR
        self.max_results_per_user = ConfigClass.MAX_RESULTS_PER_USER
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if not self.enabled:
            logger.info("Twitter API功能已禁用")
            return False
        
        if not self.bearer_token:
            logger.error("未设置Twitter Bearer Token，请检查配置文件")
            return False
        
        if not self.target_users:
            logger.error("未设置目标用户列表，请在配置文件中提供要监控的用户")
            return False
        
        return True
    
    def __str__(self) -> str:
        """配置信息字符串表示"""
        return (
            f"Twitter配置:\n"
            f"  启用状态: {self.enabled}\n"
            f"  目标用户: {', '.join(self.target_users)}\n"
            f"  检查间隔: {self.interval_minutes}分钟\n"
            f"  输出目录: {self.output_dir}\n"
            f"  每用户获取推文数: {self.max_results_per_user}"
        )


class TwitterAPI:
    """X平台API客户端，用于获取指定用户的最新推文"""
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, bearer_token: str):
        """
        初始化TwitterAPI客户端
        
        Args:
            bearer_token: X API的认证令牌
        """
        self.bearer_token = bearer_token
        self.headers = {
            "Authorization": f"Bearer {bearer_token}"
        }
    
    def get_user_timeline(self, user_id: str, max_results: int = 1, 
                         pagination_token: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定用户的时间线（最新推文）
        
        Args:
            user_id: 用户ID
            max_results: 每页返回的最大结果数
            pagination_token: 分页标记
            
        Returns:
            包含推文数据的字典
        """
        endpoint = f"{self.BASE_URL}/users/{user_id}/tweets"
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,text",
            "expansions": "author_id",
            "user.fields": "username,name,created_at"
        }
        
        if pagination_token:
            params["pagination_token"] = pagination_token
            
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取用户 {user_id} 的推文时出错: {str(e)}")
            return {"error": str(e)}

    def get_users_by_usernames(self, usernames: List[str]) -> Dict[str, Any]:
        """
        通过用户名获取用户ID
        
        Args:
            usernames: 用户名列表
            
        Returns:
            包含用户数据的字典
        """
        endpoint = f"{self.BASE_URL}/users/by"
        usernames_str = ",".join(usernames)
        params = {
            "usernames": usernames_str,
            "user.fields": "username,name,created_at"
        }
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取用户ID时出错: {str(e)}")
            return {"error": str(e)}


class TwitterMonitor:
    """监控指定用户的最新推文并定时更新"""
    
    def __init__(self, config: TwitterConfig):
        """
        初始化TwitterMonitor
        
        Args:
            config: Twitter配置对象
        """
        self.config = config
        self.api = TwitterAPI(config.bearer_token)
        self.user_ids = {}  # 用户名到ID的映射
        self.last_tweet_ids = {}  # 每个用户的最后一条推文ID
        
        # 确保输出目录存在
        os.makedirs(config.output_dir, exist_ok=True)
    
    def resolve_user_ids(self):
        """将用户名解析为用户ID"""
        users_data = self.api.get_users_by_usernames(self.config.target_users)
        
        if "data" in users_data:
            for user in users_data["data"]:
                self.user_ids[user["username"]] = user["id"]
                logger.info(f"已解析用户 @{user['username']} 的ID: {user['id']}")
        
        if "errors" in users_data:
            for error in users_data["errors"]:
                logger.error(f"解析用户名时出错: {error}")
    
    def fetch_latest_tweets(self):
        """获取所有目标用户的最新推文"""
        logger.info(f"开始获取 {len(self.user_ids)} 个用户的最新推文")
        
        for username, user_id in self.user_ids.items():
            try:
                # 获取用户最新的推文
                tweets_data = self.api.get_user_timeline(
                    user_id, 
                    max_results=self.config.max_results_per_user
                )
                
                if "data" in tweets_data:
                    # 将结果保存到文件
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{self.config.output_dir}/{username}_{timestamp}.json"
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(tweets_data, f, ensure_ascii=False, indent=2)
                    
                    # 更新最后一条推文ID
                    if tweets_data["data"]:
                        newest_id = tweets_data["data"][0]["id"]
                        prev_id = self.last_tweet_ids.get(username)
                        
                        if prev_id != newest_id:
                            logger.info(f"用户 @{username} 有新推文，ID: {newest_id}")
                        
                        self.last_tweet_ids[username] = newest_id
                    
                    logger.info(f"已获取并保存用户 @{username} 的 {len(tweets_data['data'])} 条推文")
                else:
                    logger.warning(f"用户 @{username} 没有推文数据返回")
                
                # 避免API速率限制
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"处理用户 @{username} 的推文时出错: {str(e)}")
    
    def start_monitoring(self):
        """开始定时监控"""
        # 首先解析用户ID
        self.resolve_user_ids()
        
        if not self.user_ids:
            logger.error("没有成功解析任何用户ID，无法开始监控")
            return
        
        # 立即执行一次
        self.fetch_latest_tweets()
        
        # 设置定时任务
        schedule.every(self.config.interval_minutes).minutes.do(self.fetch_latest_tweets)
        
        logger.info(f"已开始监控 {len(self.user_ids)} 个用户的推文，间隔: {self.config.interval_minutes} 分钟")
        
        # 持续运行定时任务
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("推文监控已停止")


def main():
    """主函数"""
    # 加载配置
    config = TwitterConfig()
    
    # 打印当前配置
    logger.info(config)
    
    # 检查配置是否有效
    if not config.is_valid():
        return
    
    # 创建并启动监控器
    monitor = TwitterMonitor(config=config)
    monitor.start_monitoring()


if __name__ == "__main__":
    main()
