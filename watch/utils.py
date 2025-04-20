import asyncio
import logging
import time
from urllib.parse import urljoin
from datetime import timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

# === Настройки ===
BASE_URL = "https://lombard-perspectiva.ru"
try:
    USER_AGENT = UserAgent().random
except Exception:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

MAX_CONCURRENT_TASKS = 10
REQUEST_TIMEOUT = 10_000
HEADLESS = True
VIEWPORT = {"width": 600, "height": 400}
PROXY = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# === Таймер ===
class ParserTimer:
    def __init__(self):
        self.start_time = None

    def start(self):
        self.start_time = time.perf_counter()
        logger.info("⏱ Начало парсинга")

    def stop(self):
        return time.perf_counter() - self.start_time


# === Основной универсальный парсер ===
async def parse_products_page(page_num: int, items_limit: int = None) -> list:
    try:
        return await parse_with_playwright(page_num, items_limit)
    except Exception as e:
        logger.warning(f"⚠️ Playwright не сработал: {e} — fallback на bs4")
        return await parse_with_bs4(page_num, items_limit)


# === Парсинг через Playwright ===
async def parse_with_playwright(page_num: int, items_limit: int = None) -> list:
    timer = ParserTimer()
    timer.start()

    async with async_playwright() as p:
        launch_args = {
            "headless": HEADLESS,
            "args": [
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--single-process",
                "--disable-background-networking",
                "--disable-breakpad",
                "--disable-extensions",
                "--disable-sync",
                "--no-zygote",
            ],
            "timeout": 60_000,
        }
        if PROXY:
            launch_args["proxy"] = {"server": PROXY}

        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="ru-RU",
            ignore_https_errors=True,
        )
        main_page = await context.new_page()
        try:
            url = f"{BASE_URL}/clocks_today/"
            if page_num > 1:
                url = f"{BASE_URL}/clocks_today/page/{page_num}/"

            await main_page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
            await main_page.wait_for_selector("a.product-list-item", timeout=30000)
            if await main_page.query_selector("div#recaptcha"):
                raise Exception("Капча")

            links = await main_page.evaluate('''() =>
                Array.from(document.querySelectorAll('a.product-list-item'))
                    .map(a => a.href)
                    .filter(Boolean)
            ''')

            product_links = [urljoin(BASE_URL, link) for link in links if link]
            if not product_links:
                raise Exception("Ссылки на товары не найдены")

            if items_limit:
                product_links = product_links[:items_limit]

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            tasks = [get_product_data_playwright(context, link, semaphore) for link in product_links]
            results_raw = await asyncio.gather(*tasks)
            results = [r for r in results_raw if r]

            elapsed = timer.stop()
            logger.info(f"✅ [Playwright] Получено {len(results)} товаров за {timedelta(seconds=elapsed)}")
            return results

        finally:
            await main_page.close()
            await context.close()
            await browser.close()


async def get_product_data_playwright(context, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
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
            logger.error(f"[Playwright] Ошибка ({url[-15:]}): {str(e)}")
            return None
        finally:
            await page.close()


# === Fallback: Парсинг через httpx + bs4 ===
async def parse_with_bs4(page_num: int, items_limit: int = None) -> list:
    timer = ParserTimer()
    timer.start()

    try:
        url = f"{BASE_URL}/clocks_today/"
        if page_num > 1:
            url = f"{BASE_URL}/clocks_today/page/{page_num}/"

        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT / 1000) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        anchors = soup.select("a.product-list-item")
        product_links = [urljoin(BASE_URL, a.get("href")) for a in anchors if a.get("href")]

        if not product_links:
            raise Exception("Ссылки на товары не найдены")

        if items_limit:
            product_links = product_links[:items_limit]

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT / 1000, headers=headers) as client:
            tasks = [get_product_data_bs4(client, url, semaphore) for url in product_links]
            results_raw = await asyncio.gather(*tasks)
            results = [r for r in results_raw if r]

        elapsed = timer.stop()
        logger.info(f"✅ [BS4] Получено {len(results)} товаров за {timedelta(seconds=elapsed)}")
        return results

    except Exception as e:
        logger.error(f"Критическая ошибка при bs4-парсинге: {e}")
        return []


async def get_product_data_bs4(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
    async with semaphore:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            name_tag = soup.select_one('h1[itemprop="name"]')
            image_tag = soup.select_one('img[itemprop="image"]')

            if not name_tag or not image_tag:
                return None

            name = name_tag.get_text(strip=True)
            image = image_tag.get("src") or image_tag.get("data-src") or ""

            return {
                "name": name,
                "url": url,
                "image": image
            }
        except Exception as e:
            logger.error(f"[BS4] Ошибка ({url[-15:]}): {str(e)}")
            return None



#
# import asyncio
# import logging
# import time
# from urllib.parse import urljoin
# from datetime import timedelta
# from typing import Optional
# from fake_useragent import UserAgent
# from playwright.async_api import async_playwright
#
# BASE_URL = "https://lombard-perspectiva.ru"
# try:
#     USER_AGENT = UserAgent().random
# except Exception:
#     USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
#
# # USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
# MAX_CONCURRENT_TASKS = 10
# REQUEST_TIMEOUT = 10_000
# HEADLESS = True
# VIEWPORT = {'width': 600, 'height': 400}
# PROXY = None
#
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)
#
# class ParserTimer:
#     def __init__(self):
#         self.start_time = None
#
#     def start(self):
#         self.start_time = time.perf_counter()
#         logger.info("⏱ Начало парсинга")
#
#     def stop(self):
#         return time.perf_counter() - self.start_time
# async def get_product_links(page, page_num: int, retries=3) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#     for attempt in range(retries):
#         try:
#             await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
#             await page.wait_for_selector('a.product-list-item', timeout=30000)
#             if await page.query_selector('div#recaptcha'):
#                 raise Exception("Капча")
#
#             links = await page.evaluate('''() =>
#                 Array.from(document.querySelectorAll('a.product-list-item'))
#                     .map(a => a.href)
#                     .filter(Boolean)
#             ''')
#             return [urljoin(BASE_URL, link) for link in links if link]
#         except Exception as e:
#             logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
#             if attempt == retries - 1:
#                 return []
#
#
# async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
#     async with semaphore:
#         page = await context.new_page()
#         try:
#             await page.goto(url, wait_until="domcontentloaded", timeout=30000)
#             await page.wait_for_selector('img[itemprop="image"]', timeout=30000)
#
#             product_data = await page.evaluate('''() => {
#                 const h1 = document.querySelector('h1[itemprop="name"]');
#                 const img = document.querySelector('img[itemprop="image"]');
#                 if (!h1 || !img) return null;
#                 const src = img.currentSrc || img.src || img.getAttribute('data-src') || '';
#                 return {
#                     name: h1.textContent.trim(),
#                     url: window.location.href,
#                     image: src
#                 };
#             }''')
#             return product_data
#         except Exception as e:
#             logger.error(f"Ошибка ({url[-15:]}): {str(e)}")
#             return None
#         finally:
#             await page.close()
#
#
# async def parse_products_page(page_num: int, items_limit: int = None) -> list:
#     timer = ParserTimer()
#     timer.start()
#     playwright = await async_playwright().start()  # Явный запуск playwright
#     browser = None
#     context = None
#
#     async with async_playwright() as p:
#         launch_args = {
#             "headless": HEADLESS,
#             "args": [
#                 "--disable-gpu",
#                 "--disable-dev-shm-usage",  # важно для Docker
#                 "--no-sandbox",
#                 "--single-process",
#                 "--disable-dev-shm-usage",  # уже есть, но это важно
#                 "--disable-background-networking",
#                 "--disable-background-timer-throttling",
#                 "--disable-breakpad",
#                 "--disable-client-side-phishing-detection",
#                 "--disable-component-update",
#                 "--disable-default-apps",
#                 "--disable-domain-reliability",
#                 "--disable-extensions",
#                 "--disable-features=site-per-process",
#                 "--disable-hang-monitor",
#                 "--disable-popup-blocking",
#                 "--disable-prompt-on-repost",
#                 "--disable-sync",
#                 "--disable-translate",
#                 "--metrics-recording-only",
#                 "--no-first-run",
#                 "--safebrowsing-disable-auto-update",
#                 "--no-zygote",
#             ],
#             "timeout": 60_000
#         }
#         if PROXY:
#             launch_args["proxy"] = {"server": PROXY}
#
#         browser = await p.chromium.launch(**launch_args)
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             viewport=VIEWPORT,
#             locale='ru-RU',
#             ignore_https_errors=True
#         )
#         main_page = await context.new_page()
#         try:
#             product_links = await get_product_links(main_page, page_num)
#             if main_page.is_closed():
#                 logger.warning(f"Страница уже закрыта: {url}")
#                 return None
#             if items_limit:
#                 product_links = product_links[:items_limit]
#             semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
#             tasks = [get_product_data(context, link, semaphore) for link in product_links]
#             results_raw = await asyncio.gather(*tasks)
#             results = [r for r in results_raw if r]
#             elapsed = timer.stop()
#             logger.info(f"✅ {len(results)} товаров за {timedelta(seconds=elapsed)}")
#             return results
#         finally:
#             await main_page.close()
#             await context.close()
#             await browser.close()
