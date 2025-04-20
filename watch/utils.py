import asyncio
import logging
import time
from urllib.parse import urljoin
from datetime import timedelta
from typing import Optional
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

BASE_URL = "https://lombard-perspectiva.ru"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
MAX_CONCURRENT_TASKS = 10
REQUEST_TIMEOUT = 10_000
HEADLESS = True
VIEWPORT = {'width': 400, 'height': 300}
PROXY = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ParserTimer:
    def __init__(self):
        self.start_time = None

    def start(self):
        self.start_time = time.perf_counter()
        logger.info("⏱ Начало парсинга")

    def stop(self):
        return time.perf_counter() - self.start_time

async def get_product_links(page, page_num: int, retries=3) -> list:
    url = f"{BASE_URL}/clocks_today/?page={page_num}"
    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
            html = await page.content()
            logger.debug(f"HTML content of product page:\n{html[:1000]}...")
            await page.wait_for_selector('a.product-list-item', timeout=30000)
            if await page.query_selector('div#recaptcha'):
                raise Exception("Капча")

            links = await page.evaluate('''() =>
                Array.from(document.querySelectorAll('a.product-list-item'))
                    .map(a => a.href)
                    .filter(Boolean)
            ''')
            return [urljoin(BASE_URL, link) for link in links if link]
        except Exception as e:
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt == retries - 1:
                return []

async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
    async with semaphore:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector('img[itemprop="image"]', timeout=30000)

            product_data = await page.evaluate('''() => {
                const h1 = document.querySelector('h1[itemprop="name"]');
                const img = document.querySelector('img[itemprop="image"]');
                if (!h1 || !img) return null;
                const src = img.currentSrc || img.src || img.getAttribute('data-src') || '';
                return {
                    name: h1.textContent.trim(),
                    url: window.location.href,
                    image: src
                };
            }''')
            return product_data
        except Exception as e:
            logger.error(f"Ошибка ({url[-15:]}): {str(e)}")
            return None
        finally:
            await page.close()

async def parse_products_page(page_num: int, items_limit: int = None) -> list:
    timer = ParserTimer()
    timer.start()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox",
                      "--disable-gpu",
                      "--disable-extensions",
                      "--disable-setuid-sandbox",
                      "--disable-infobars",
                      "--single-process",
                      "--disable-accelerated-2d-canvas",
                      "--disable-dev-tools",
                      "--disable-features=site-per-process",
                      "--disable-dev-shm-usage",  # важно для Docker
                      "--single-process",
                      "--disable-background-networking",
                      "--disable-background-timer-throttling",
                      "--disable-breakpad",
                      "--disable-client-side-phishing-detection",
                      "--disable-component-update",
                      "--disable-default-apps",
                      "--disable-domain-reliability",
                      "--disable-extensions",
                      "--disable-hang-monitor",
                      "--disable-popup-blocking",
                      "--disable-prompt-on-repost",
                      "--disable-sync",
                      "--disable-translate",
                      "--metrics-recording-only",
                      "--no-first-run",
                      "--safebrowsing-disable-auto-update",
                      "--no-zygote",
                      ]
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
                locale='ru-RU',
                ignore_https_errors=True
            )
            main_page = await context.new_page()
            product_links = await get_product_links(main_page, page_num)

            if not product_links:
                logger.warning("❌ Ссылки на товары не найдены")
                await main_page.close()
                await context.close()
                await browser.close()
                return []

            if items_limit:
                product_links = product_links[:items_limit]

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            tasks = [get_product_data(context, link, semaphore) for link in product_links]
            results_raw = await asyncio.gather(*tasks)
            results = [r for r in results_raw if r]

            await main_page.close()
            await asyncio.sleep(1)  # небольшая задержка перед закрытием

            elapsed = timer.stop()
            logger.info(f"✅ {len(results)} товаров за {timedelta(seconds=elapsed)}")

            await context.close()
            await browser.close()

            return results

    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге: {e}")
        return []
