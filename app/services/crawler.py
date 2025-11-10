import httpx
from typing import Optional, Dict, Any
from app.core.config import settings


class CrawlerService:
    """爬虫服务类"""
    
    def __init__(self):
        self.timeout = 30.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def fetch_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        获取 URL 内容
        
        Args:
            url: 要抓取的 URL
            
        Returns:
            包含响应数据的字典，失败返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                response.raise_for_status()
                
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "content": response.text[:1000],  # 限制内容长度
                    "headers": dict(response.headers),
                }
        except httpx.HTTPError as e:
            print(f"HTTP 错误: {e}")
            return None
        except Exception as e:
            print(f"抓取错误: {e}")
            return None
    
    async def crawl_multiple(self, urls: list[str]) -> list[Dict[str, Any]]:
        """
        批量抓取多个 URL
        
        Args:
            urls: URL 列表
            
        Returns:
            抓取结果列表
        """
        results = []
        for url in urls:
            result = await self.fetch_url(url)
            if result:
                results.append(result)
        return results


# 创建服务实例
crawler_service = CrawlerService()

