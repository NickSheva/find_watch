import asyncio
from tqdm.asyncio import tqdm
from playwright.async_api import async_playwright
from urllib.parse import urljoin
import logging
import time
from typing import Optional
from datetime import timedelta
from fake_useragent import UserAgent
import argparse
import sys
import tqdm

# Настройка логирования

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_logging(log_file=None):
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    logging.getLogger('playwright').setLevel(logging.WARNING)

# Константы
BASE_URL = "https://lombard-perspectiva.ru"
try:
    USER_AGENT = UserAgent().random
except Exception:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

MAX_CONCURRENT_TASKS = 10
REQUEST_TIMEOUT = 10_000  # 2 мин
HEADLESS = True
VIEWPORT = {'width': 600, 'height': 400}
PROXY = None  # пример: "http://login:pass@ip:port"

class ParserTimer:
    def __init__(self):
        self.start_time = None

    def start(self):
        self.start_time = time.perf_counter()
        logger.info("⏱ Начало парсинга")

    def stop(self):
        return time.perf_counter() - self.start_time

async def block_resources(route):
    # 'image'
    if route.request.resource_type in {'stylesheet', 'font'}:
        await route.abort()
    else:
        await route.continue_()

async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
    async with semaphore:
        page = await context.new_page()
        try:
            # await page.route('**/*.{png,jpg,jpeg,webp,svg,gif,css,woff2}', block_resources)
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        #     logger.info("✅ Страница загружена")
        # except Exception as e:
        #     logger.error(f"❌ GOTO провалился: {e}")
        # try:
            await page.wait_for_selector('img[itemprop="image"]', timeout=15000)

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

            # Подсчёт прогресса

            if product_data:
                logger.info(f"✅ Успешно: {product_data['name'][:30]}...")
                return product_data
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка ({url[-15:]}): {str(e)[:50]}...")
            return None
        finally:
            await page.close()

async def get_product_links(page, page_num: int, retries=3) -> list:
    url = f"{BASE_URL}/clocks_today/?page={page_num}"
    logger.info(f"🌐 Загрузка страницы {page_num}")

    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
            await page.wait_for_selector('a.product-list-item', timeout=15000)

            if await page.query_selector('div#recaptcha'):
                raise Exception("Обнаружена капча")

            links = await page.evaluate('''() =>
                Array.from(document.querySelectorAll('a.product-list-item'))
                    .map(a => a.href)
                    .filter(Boolean)
            ''')

            found_links = [urljoin(BASE_URL, link) for link in links if link]
            logger.info(f"🔗 Найдено {len(found_links)} товаров на странице {page_num}")
            return found_links

        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
            if attempt == retries - 1:
                logger.error(f"❌ Ошибка при загрузке страницы {page_num}: {e}")
                return []

async def parse_products_page(page_num: int, items_limit: int = None, on_progress=None):
    timer = ParserTimer()
    timer.start()

    async with async_playwright() as p:
        launch_args = {
            "headless": HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        }
        if PROXY:
            launch_args["proxy"] = {"server": PROXY}

        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            java_script_enabled=True,
            ignore_https_errors=True,
            viewport=VIEWPORT,
            locale='ru-RU',
        )

        main_page = await context.new_page()
        try:
            product_links = await get_product_links(main_page, page_num)
            if items_limit:
                product_links = product_links[:items_limit]

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            # прогресс-бар по ссылкам
            tasks = [get_product_data(context, link, semaphore) for link in product_links]
            # tqdm.gather(*tasks) заменяет обычный asyncio.gather, но показывает прогресс.
            # ncols=80 — ширина прогресс-бара, можешь подогнать под консоль.
            # desc — заголовок для прогресса.
            try:
                results_raw = await asyncio.gather(*tasks)
                # results_raw = await tqdm.gather(*tasks, desc="📦 Парсинг", ncols=80)
            except RuntimeError as e:
                logger.warning(f"Async error (interpreter shutdown?): {e}")
                results_raw = []
            # result_raw = await tqdm.gather(*tasks, desk="Парсинг товаров", ncols=80)

            results = [r for r in results_raw if r]

            elapsed = timer.stop()
            logger.info(f"📊 Статистика: {len(results)} товаров за {timedelta(seconds=elapsed)}")
            return results

        except Exception as e:
            logger.error(f"🔥 Критическая ошибка при парсинге: {str(e)}")
            return []

        finally:
            await main_page.close()
            await context.close()
            await browser.close()

async def cli_main(args):
    setup_logging(args.log_file)

    try:
        logger.info(f"🚀 Запуск парсера: страница {args.page}, лимит {args.limit}")
        results = await parse_products_page(page_num=args.page, items_limit=args.limit)

        print("\n" + "=" * 50)
        print(f"Всего получено {len(results)} результатов:")
        for i, item in enumerate(results[:5], 1):
            print(f"""{i}.
            <div class="catalog-item">
              <img src="{item['image']}" alt="{item['name']}" loading="lazy" itemprop="image" class="catalog-item-img--object">
              <h3>{item['name']}</h3>
              <a href="{item['url']}">Смотреть</a>
            </div>""")
        # {item['name']} - {item['url']}")
        # if len(results) > 5:
        #     print(f"... и еще {len(results) - 5} товаров")
        # print("=" * 50 + "\n")

        return 0

    except Exception as e:
        logger.error(f"💥 Ошибка: {str(e)}", exc_info=True)
        return 1
    finally:
        logger.info("🛑 Завершение работы парсера")

def parse_cli_args():
    parser = argparse.ArgumentParser(
        description="🕵️ Парсер сайта lombard-perspectiva.ru",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--page', type=int, default=1, help='Номер страницы каталога')
    parser.add_argument('--limit', type=int, default=None, help='Максимальное количество товаров для парсинга')
    parser.add_argument('--log-file', type=str, default=None, help='Файл для сохранения логов (опционально)')
    return parser.parse_args()

if __name__ == "__main__":
    setup_logging()
    args = parse_cli_args()
    sys.exit(asyncio.run(cli_main(args)))
