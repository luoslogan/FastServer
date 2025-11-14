from typing import Optional, Dict, Any

import httpx
from loguru import logger

from app.core.config import settings
from app.core.logging import register_module_logger

# 为爬虫服务注册单独的日志文件 (可选, 如果需要单独记录爬虫日志)
# 如果不调用这行, 日志会正常记录到 app.log
# register_module_logger(__name__, "crawler.log", log_level="DEBUG")


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
            logger.debug(f"开始抓取 URL: {url}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, headers=self.headers, follow_redirects=True
                )
                response.raise_for_status()

                logger.info(f"成功抓取 URL: {url}, 状态码: {response.status_code}")
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "content": response.text[:1000],  # 限制内容长度
                    "headers": dict(response.headers),
                }
        except httpx.HTTPError as e:
            logger.error(f"HTTP 错误: {url}, 错误: {e}")
            return None
        except Exception as e:
            logger.exception(f"抓取错误: {url}")
            return None

    async def crawl_multiple(self, urls: list[str]) -> list[Dict[str, Any]]:
        """
        批量抓取多个 URL

        Args:
            urls: URL 列表

        Returns:
            抓取结果列表
        """
        logger.info(f"开始批量抓取, 共 {len(urls)} 个 URL")
        results = []
        for url in urls:
            result = await self.fetch_url(url)
            if result:
                results.append(result)
        logger.info(f"批量抓取完成, 成功 {len(results)}/{len(urls)} 个")
        return results


# 创建服务实例
crawler_service = CrawlerService()
