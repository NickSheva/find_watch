

# import asyncio
# from playwright.async_api import async_playwright
# from urllib.parse import urljoin
# import logging
# import time
# from datetime import timedelta
# from fake_useragent import UserAgent
# import aiohttp
# import argparse
# import sys
#
# # Настройка логирования
# logger = logging.getLogger(__name__)
#
#
# def setup_logging(log_file=None):
#     """Настройка системы логирования"""
#     handlers = [logging.StreamHandler(sys.stdout)]
#     if log_file:
#         handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
#
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(levelname)s - %(message)s',
#         handlers=handlers
#     )
#     # Уменьшаем логирование playwright
#     logging.getLogger('playwright').setLevel(logging.WARNING)
#
#
# BASE_URL = "https://lombard-perspectiva.ru"
# try:
#     USER_AGENT = UserAgent().random
# except Exception:
#     USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
# MAX_CONCURRENT_TASKS = 10  # Увеличено количество одновременных задач
# REQUEST_TIMEOUT = 12_0000  # 30 секунд таймаут
#
#
# class ParserTimer:
#     """Класс для измерения времени выполнения"""
#
#     def __init__(self):
#         self.start_time = None
#
#     def start(self):
#         self.start_time = time.perf_counter()
#         logger.info("⏱ Начало парсинга")
#
#     def elapsed(self):
#         return time.perf_counter() - self.start_time
#
#
# async def block_resources(route):
#     """Блокировка ненужных ресурсов для ускорения загрузки"""
#     if route.request.resource_type in {'image', 'stylesheet', 'font'}:
#         await route.abort()
#     else:
#         await route.continue_()
#
#
# async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> dict | None:
#     """Получение данных о продукте"""
#     async with semaphore:
#         page = await context.new_page()
#         try:
#             # Блокируем ненужные ресурсы
#             await page.route('**/*.{png,jpg,jpeg,webp,svg,gif,css,woff2}', block_resources)
#
#             await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
#
#             # Комбинированный запрос данных
#             product_data = await page.evaluate('''() => {
#                 const h1 = document.querySelector('h1[itemprop="name"]');
#                 if (!h1) return null;
#                 return {
#                     name: h1.textContent.trim(),
#                     url: window.location.href
#                 };
#             }''')
#
#             if product_data:
#                 logger.info(f"✅ Успешно: {product_data['name'][:30]}...")
#                 return product_data
#             return None
#
#         except Exception as e:
#             logger.error(f"❌ Ошибка ({url[-15:]}): {str(e)[:50]}...")
#             return None
#         finally:
#             await page.close()
#
#
# USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# # Можно подставить прокси, если нужно:
# PROXY = None  # например: "http://login:pass@ip:port"
#
# async def get_product_links(page, page_num: int, retries=3) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#     logger.info(f"🌐 Загрузка страницы {page_num}")
#
#     for attempt in range(retries):
#         try:
#             await page.goto(url, wait_until="domcontentloaded", timeout=120000)
#             await page.wait_for_selector('a.product-list-item', timeout=15000)
#
#             if await page.query_selector('div#recaptcha'):
#                 raise Exception("Обнаружена капча")
#
#             links = await page.evaluate('''() =>
#                 Array.from(document.querySelectorAll('a.product-list-item'))
#                 .map(a => a.href)
#                 .filter(Boolean)
#             ''')
#
#             found_links = [urljoin(BASE_URL, link) for link in links if link]
#             logger.info(f"🔗 Найдено {len(found_links)} товаров на странице {page_num}")
#             return found_links
#
#         except Exception as e:
#             logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
#             if attempt == retries - 1:
#                 logger.error(f"❌ Ошибка при загрузке страницы {page_num}: {e}")
#                 return []
#
# async def parse_products_page(page_num: int, items_limit: int = None):
#     timer = ParserTimer()
#     timer.start()
#
#     async with async_playwright() as p:
#         launch_args = {
#             "headless": False,  # чтобы видеть, что происходит
#             "args": [
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-setuid-sandbox",
#                 "--disable-dev-shm-usage",
#                 "--disable-gpu",
#             ]
#         }
#
#         if PROXY:
#             launch_args["proxy"] = {"server": PROXY}
#
#         browser = await p.chromium.launch(**launch_args)
#
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             viewport={'width': 1280, 'height': 800},
#             locale='ru-RU',
#         )
#
#         main_page = await context.new_page()
#
#         try:
#             product_links = await get_product_links(main_page, page_num)
#             if items_limit:
#                 product_links = product_links[:items_limit]
#
#             semaphore = asyncio.Semaphore(5)
#
#             tasks = [
#                 get_product_data(context, link, semaphore)
#                 for link in product_links
#             ]
#             results_raw = await asyncio.gather(*tasks)
#             results = [r for r in results_raw if r]
#
#             elapsed = timer.stop()
#             logger.info(f"📊 Статистика: {len(results)} товаров за {timedelta(seconds=elapsed)}")
#             return results
#
#         except Exception as e:
#             logger.error(f"🔥 Критическая ошибка при парсинге: {str(e)}")
#             return []
#
#         finally:
#             await main_page.close()
#             await context.close()
#             await browser.close()
#
# async def cli_main(args):
#     """Точка входа для CLI"""
#     setup_logging(args.log_file)
#
#     try:
#         logger.info(f"🚀 Запуск парсера: страница {args.page}, лимит {args.limit}")
#         results = await parse_products_page(
#             page_num=args.page,
#             items_limit=args.limit
#         )
#
#         print("\n" + "=" * 50)
#         print(f"Всего получено {len(results)} результатов:")
#         for i, item in enumerate(results[:5], 1):  # Выводим только первые 5 для примера
#             print(f"{i}. {item['name']} - {item['url']}")
#         if len(results) > 5:
#             print(f"... и еще {len(results) - 5} товаров")
#         print("=" * 50 + "\n")
#
#         return 0
#     except Exception as e:
#         logger.error(f"💥 Ошибка: {str(e)}", exc_info=True)
#         return 1
#     finally:
#         logger.info("🛑 Завершение работы парсера")
#
#
# def parse_cli_args():
#     """Разбор аргументов командной строки"""
#     parser = argparse.ArgumentParser(
#         description="🕵️ Парсер сайта lombard-perspectiva.ru",
#         formatter_class=argparse.ArgumentDefaultsHelpFormatter
#     )
#     parser.add_argument(
#         '--page',
#         type=int,
#         default=1,
#         help='Номер страницы каталога'
#     )
#     parser.add_argument(
#         '--limit',
#         type=int,
#         default=None,
#         help='Максимальное количество товаров для парсинга'
#     )
#     parser.add_argument(
#         '--log-file',
#         type=str,
#         default=None,
#         help='Файл для сохранения логов (опционально)'
#     )
#     return parser.parse_args()
#
#
# if __name__ == "__main__":
#     args = parse_cli_args()
#     sys.exit(asyncio.run(cli_main(args)))



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
REQUEST_TIMEOUT = 120_000  # 2 мин
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
            await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
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



 # try:
 #            product_links = await get_product_links(main_page, page_num)
 #            if items_limit:
 #                product_links = product_links[:items_limit]
 #
 #            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
 #
 #            results = []
 #            total_links = len(product_links)
 #
 #            for idx, link in enumerate(product_links):
 #                result = await get_product_data(context, link, semaphore)
 #                if result:
 #                    results.append(result)
 #                if on_progress:
 #                    await on_progress(idx + 1, total_links)
 #
 #            elapsed = timer.stop()
 #            logger.info(f"📊 Спаршено: {len(results)} товаров за {timedelta(seconds=elapsed)}")
 #            return results
 #
 #        except Exception as e:
 #            logger.error(f"🔥 Ошибка: {str(e)}")
 #            return []
 #
 #        finally:
 #            await main_page.close()
 #            await context.close()
 #            await browser.close()



# import asyncio
# from playwright.async_api import async_playwright
# from urllib.parse import urljoin
# import logging
# import time
# from datetime import timedelta
# from fake_useragent import UserAgent
#
# # Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
#
# BASE_URL = "https://lombard-perspectiva.ru"
# USER_AGENT = UserAgent().random
#
#
# class ParserTimer:
#     def __init__(self):
#         self.start_time = None
#         self.end_time = None
#
#     def start(self):
#         self.start_time = time.time()
#         logger.info("⏱ Начало парсинга")
#
#     def stop(self):
#         self.end_time = time.time()
#         elapsed = self.end_time - self.start_time
#         logger.info(f"⏱ Парсинг завершен. Затраченное время: {timedelta(seconds=elapsed)}")
#         return elapsed
#
#
# async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> dict | None:
#     async with semaphore:
#         page = await context.new_page()
#         try:
#             await page.goto(url, wait_until="domcontentloaded", timeout=80000)
#             h1 = await page.wait_for_selector('h1[itemprop="name"]', timeout=15000)
#             name = await h1.text_content()
#             logger.info(f"✅ Успешно загружен продукт: {name[:30]}...")
#             return {'name': name.strip(), 'url': url}
#         except Exception as e:
#             logger.error(f"❌ Ошибка при парсинге {url}: {str(e)}")
#             return None
#         finally:
#             await page.close()
#
#
# async def get_product_links(page, page_num: int, retries=2) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#     logger.info(f"🌐 Загрузка страницы {page_num}")
#
#     for attempt in range(retries):
#         try:
#             await page.goto(url, wait_until="load", timeout=70000)
#             await page.wait_for_selector('a.product-list-item', timeout=15000)
#
#             if await page.query_selector('div#recaptcha'):
#                 raise Exception("Обнаружена капча")
#
#             links = await page.evaluate('''() =>
#                 Array.from(document.querySelectorAll('a.product-list-item'))
#                 .map(a => a.href)
#                 .filter(Boolean)
#                 ''')
#
#             # links = await page.eval_on_selector_all(
#             #     'a.product-list-item',
#             #     "elements => elements.map(el => el.href)"
#             # )
#             found_links = [urljoin(BASE_URL, link) for link in links if link]
#             logger.info(f"🔗 Найдено {len(found_links)} товаров на странице {page_num}")
#             return found_links
#         except Exception as e:
#             logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
#             if attempt == retries - 1:
#                 logger.error(f"❌ Ошибка при загрузке страницы {page_num}: {e}")
#                 return []
#             # await asyncio.sleep(.4)  # пауза между попытками
#
#
# async def parse_products_page(page_num: int, items_limit: int = None):
#     timer = ParserTimer()
#     timer.start()
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(
#             headless=True,
#             args=[
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-setuid-sandbox",
#                 "--disable-dev-shm-usage",
#                 "--disable-gpu",
#             ]
#         )
#
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             viewport={'width': 1280, 'height': 800},
#             locale='ru-RU',
#         )
#
#         main_page = await context.new_page()
#
#         try:
#             product_links = await get_product_links(main_page, page_num)
#             if items_limit:
#                 product_links = product_links[:items_limit]
#
#             semaphore = asyncio.Semaphore(5)  # максимум 5 одновременных запросов
#
#             tasks = [
#                 get_product_data(context, link, semaphore)
#                 for link in product_links
#             ]
#             results_raw = await asyncio.gather(*tasks)
#
#             results = [r for r in results_raw if r]
#
#             elapsed = timer.stop()
#             logger.info(f"📊 Статистика: {len(results)} товаров за {timedelta(seconds=elapsed)}")
#             return results
#
#         except Exception as e:
#             logger.error(f"🔥 Критическая ошибка при парсинге: {str(e)}")
#             return []
#
#         finally:
#             await main_page.close()
#             await context.close()
#             await browser.close()
#
#
# async def main():
#     try:
#         logger.info("🚀 Запуск парсера")
#         results = await parse_products_page(page_num=1, items_limit=20)
#
#         print("\n" + "=" * 50)
#         print(f"Всего получено {len(results)} результатов:")
#         for i, item in enumerate(results, 1):
#             print(f"{i}. {item['name']} - {item['url']}")
#         print("=" * 50 + "\n")
#
#     except Exception as e:
#         logger.error(f"💥 Ошибка в main: {str(e)}")
#     finally:
#         logger.info("🛑 Завершение работы парсера")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())

# import asyncio
# from playwright.async_api import async_playwright
# from urllib.parse import urljoin
# import logging
# import time
# from datetime import timedelta
# from fake_useragent import UserAgent
#
# # Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
#
# BASE_URL = "https://lombard-perspectiva.ru"
# USER_AGENT = UserAgent().random
# MAX_RETRIES = 3  # Максимальное количество попыток
# TIMEOUT = 30000  # 30 секунд таймаут
#
#
# class ParserTimer:
#     def __init__(self):
#         self.start_time = None
#
#     def start(self):
#         self.start_time = time.time()
#         logger.info("⏱ Начало парсинга")
#
#     def elapsed(self):
#         return timedelta(seconds=time.time() - self.start_time)
#
#
# async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> dict | None:
#     async with semaphore:
#         page = await context.new_page()
#         try:
#             # Ускорение: отключаем загрузку ненужных ресурсов
#             await page.route('**/*.{png,jpg,jpeg,webp,svg,gif,css,woff2}', lambda route: route.abort())
#
#             await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
#
#             # Комбинированный запрос данных
#             product_data = await page.evaluate('''() => {
#                 const h1 = document.querySelector('h1[itemprop="name"]');
#                 if (!h1) return null;
#                 return {
#                     name: h1.textContent.trim(),
#                     url: window.location.href
#                 };
#             }''')
#
#             if product_data:
#                 logger.info(f"✅ Успешно: {product_data['name'][:30]}...")
#                 return product_data
#             return None
#
#         except Exception as e:
#             logger.error(f"❌ Ошибка ({url[-15:]}): {str(e)[:50]}...")
#             return None
#         finally:
#             await page.close()
#
#
# async def get_product_links(page, page_num: int) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#
#     for attempt in range(MAX_RETRIES):
#         try:
#             # Ускорение: networkidle вместо load
#             await page.goto(url, wait_until="networkidle", timeout=TIMEOUT)
#
#             # Проверка на блокировку
#             if await page.query_selector('div#recaptcha'):
#                 raise Exception("Обнаружена капча")
#
#             links = await page.evaluate('''() =>
#                 Array.from(document.querySelectorAll('a.product-list-item'))
#                     .map(a => a.href)
#                     .filter(Boolean)
#             ''')
#
#             found_links = [urljoin(BASE_URL, link) for link in links]
#             logger.info(f"🔗 Найдено {len(found_links)} товаров")
#             return found_links
#
#         except Exception as e:
#             logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {str(e)[:50]}...")
#             if attempt == MAX_RETRIES - 1:
#                 logger.error(f"❌ Ошибка страницы {page_num} после {MAX_RETRIES} попыток")
#                 return []
#             await asyncio.sleep(2 * (attempt + 1))  # Увеличиваем задержку
#
#
# async def parse_products_page(page_num: int, items_limit: int = None):
#     timer = ParserTimer()
#     timer.start()
#
#     async with async_playwright() as p:
#         # Оптимизированные параметры запуска
#         browser = await p.chromium.launch(
#             headless=True,
#             args=[
#                 "--disable-web-security",
#                 "--single-process",
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-setuid-sandbox"
#             ]
#         )
#
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             viewport={'width': 1280, 'height': 800},
#             locale='ru-RU'
#         )
#
#         page = await context.new_page()
#
#         try:
#             product_links = await get_product_links(page, page_num)
#             if items_limit and items_limit > 0:
#                 product_links = product_links[:items_limit]
#
#             logger.info(f"🚀 Начинаем парсинг {len(product_links)} товаров...")
#
#             semaphore = asyncio.Semaphore(10)  # Увеличено до 10 одновременных запросов
#
#             tasks = [get_product_data(context, link, semaphore) for link in product_links]
#             results = await asyncio.gather(*tasks)
#
#             valid_results = [r for r in results if r]
#             elapsed = timer.elapsed()
#
#             logger.info(f"⏱ Завершено за {elapsed}")
#             logger.info(f"📊 Результаты: {len(valid_results)}/{len(product_links)}")
#
#             return valid_results
#         finally:
#             await page.close()
#             await context.close()
#             await browser.close()
#
#
# async def main():
#     try:
#         logger.info("🚀 Запуск парсера")
#         results = await parse_products_page(page_num=1, items_limit=20)
#
#         print(f"\nУспешно спарсено: {len(results)} товаров")
#         if results:
#             print(f"Первый товар: {results[0]['name'][:50]}...")
#     except Exception as e:
#         logger.error(f"💥 Ошибка: {str(e)}")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())




# import asyncio
# from playwright.async_api import async_playwright
# from urllib.parse import urljoin
# import logging
# import time
# from datetime import timedelta
# from fake_useragent import UserAgent
#
# # Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
#
# BASE_URL = "https://lombard-perspectiva.ru"
# USER_AGENT = UserAgent().random
#
# class ParserTimer:
#     def __init__(self):
#         self.start_time = None
#         self.end_time = None
#
#     def start(self):
#         self.start_time = time.time()
#         logger.info("⏱ Начало парсинга")
#
#     def stop(self):
#         self.end_time = time.time()
#         elapsed = self.end_time - self.start_time
#         logger.info(f"⏱ Парсинг завершен. Затраченное время: {timedelta(seconds=elapsed)}")
#         return elapsed
#
#
# async def get_product_data(page, url: str) -> str:
#     try:
#         await page.goto(url, wait_until="domcontentloaded", timeout=20000)
#         h1 = await page.wait_for_selector('h1[itemprop="name"]', timeout=15000)
#         name = await h1.text_content()
#         logger.info(f"✅ Успешно загружен продукт: {name[:30]}...")
#         return name.strip()
#     except Exception as e:
#         logger.error(f"❌ Ошибка при парсинге {url}: {str(e)}")
#         return None
#
#
# async def get_product_links(page, page_num: int, retries=2) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#     logger.info(f"🌐 Загрузка страницы {page_num}")
#
#     for attempt in range(retries):
#         try:
#             await page.goto(url, wait_until="load", timeout=40000)
#             await page.wait_for_selector('a.product-list-item', timeout=15000)
#
#             links = await page.eval_on_selector_all(
#                 'a.product-list-item',
#                 "elements => elements.map(el => el.href)"
#             )
#             found_links = [urljoin(BASE_URL, link) for link in links if link]
#             logger.info(f"🔗 Найдено {len(found_links)} товаров на странице {page_num}")
#             return found_links
#         except Exception as e:
#             logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
#             if attempt == retries - 1:
#                 logger.error(f"❌ Ошибка при загрузке страницы {page_num}: {e}")
#                 return []
#             await asyncio.sleep(2)  # пауза между попытками
#
#
# async def parse_products_page(page_num: int, items_limit: int = None):
#     timer = ParserTimer()
#     timer.start()
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(
#             headless=True,
#             args=[
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-setuid-sandbox",
#                 "--disable-dev-shm-usage",
#                 "--disable-gpu",
#             ]
#         )
#
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             viewport={'width': 1280, 'height': 800},
#             locale='ru-RU',
#         )
#
#         page = await context.new_page()
#
#         try:
#             product_links = await get_product_links(page, page_num)
#             if items_limit:
#                 product_links = product_links[:items_limit]
#
#             results = []
#             for i, link in enumerate(product_links, 1):
#                 logger.info(f"🔄 Обработка товара {i}/{len(product_links)}")
#                 product_data = await get_product_data(page, link)
#                 if product_data:
#                     results.append({
#                         'name': product_data,
#                         'url': link
#                     })
#                 await asyncio.sleep(0.5)
#
#             elapsed = timer.stop()
#             logger.info(f"📊 Статистика: {len(results)} товаров за {timedelta(seconds=elapsed)}")
#             return results
#         except Exception as e:
#             logger.error(f"🔥 Критическая ошибка при парсинге: {str(e)}")
#             return []
#         finally:
#             await page.close()
#             await context.close()
#             await browser.close()
#
#
# async def main():
#     try:
#         logger.info("🚀 Запуск парсера")
#         results = await parse_products_page(page_num=1, items_limit=5)
#
#         print("\n" + "=" * 50)
#         print(f"Всего получено {len(results)} результатов:")
#         for i, item in enumerate(results, 1):
#             print(f"{i}. {item['name']} - {item['url']}")
#         print("=" * 50 + "\n")
#
#     except Exception as e:
#         logger.error(f"💥 Ошибка в main: {str(e)}")
#     finally:
#         logger.info("🛑 Завершение работы парсера")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())












#
# import asyncio
# from playwright.async_api import async_playwright
# from urllib.parse import urljoin
# import logging
# import time
# from datetime import timedelta
# from fake_useragent import UserAgent
#
# # Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
#
# BASE_URL = "https://lombard-perspectiva.ru"
# USER_AGENT = UserAgent().random
#
#
#
# class ParserTimer:
#     def __init__(self):
#         self.start_time = None
#         self.end_time = None
#
#     def start(self):
#         self.start_time = time.time()
#         logger.info("⏱ Начало парсинга")
#
#     def stop(self):
#         self.end_time = time.time()
#         elapsed = self.end_time - self.start_time
#         logger.info(f"⏱ Парсинг завершен. Затраченное время: {timedelta(seconds=elapsed)}")
#         return elapsed
#
#
# async def get_product_data(page, url: str) -> str:
#     try:
#         await page.goto(url, wait_until="domcontentloaded", timeout=20000)
#         h1 = await page.wait_for_selector('h1[itemprop="name"]', timeout=15000)
#         name = await h1.text_content()
#         logger.info(f"✅ Успешно загружен продукт: {name[:30]}...")
#         return name.strip()
#     except Exception as e:
#         logger.error(f"❌ Ошибка при парсинге {url}: {str(e)}")
#         return None
#
#
# async def get_product_links(page, page_num: int) -> list:
#     url = f"{BASE_URL}/clocks_today/?page={page_num}"
#     logger.info(f"🌐 Загрузка страницы {page_num}")
#
#     try:
#         await page.goto(url, wait_until="domcontentloaded", timeout=20000)
#         await page.wait_for_selector('a.product-list-item', timeout=15000)
#
#         links = await page.eval_on_selector_all(
#             'a.product-list-item',
#             "elements => elements.map(el => el.href)"
#         )
#         found_links = [urljoin(BASE_URL, link) for link in links if link]
#         logger.info(f"🔗 Найдено {len(found_links)} товаров на странице {page_num}")
#         return found_links
#     except Exception as e:
#         logger.error(f"❌ Ошибка при загрузке страницы {page_num}: {str(e)}")
#         return []
#
#
# async def parse_products_page(page_num: int, items_limit: int = None):
#     timer = ParserTimer()
#     timer.start()
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(
#             headless=True,
#             args=[
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-setuid-sandbox",
#                 "--disable-dev-shm-usage",
#                 "--disable-gpu",
#             ]
#         )
#
#         context = await browser.new_context(
#             user_agent=USER_AGENT,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#         )
#
#         page = await context.new_page()
#
#         try:
#             product_links = await get_product_links(page, page_num)
#             if items_limit:
#                 product_links = product_links[:items_limit]
#
#             results = []
#             for i, link in enumerate(product_links, 1):
#                 logger.info(f"🔄 Обработка товара {i}/{len(product_links)}")
#                 product_data = await get_product_data(page, link)
#                 if product_data:
#                     results.append({
#                         'name': product_data,
#                         'url': link
#                     })
#                 await asyncio.sleep(0.3)
#
#             elapsed = timer.stop()
#             logger.info(f"📊 Статистика: {len(results)} товаров за {timedelta(seconds=elapsed)}")
#             return results
#         except Exception as e:
#             logger.error(f"🔥 Критическая ошибка при парсинге: {str(e)}")
#             return []
#         finally:
#             await page.close()
#             await context.close()
#             await browser.close()
#
#
# async def main():
#     try:
#         logger.info("🚀 Запуск парсера")
#         results = await parse_products_page(page_num=1, items_limit=5)
#
#         print("\n" + "=" * 50)
#         print(f"Всего получено {len(results)} результатов:")
#         for i, item in enumerate(results, 1):
#             print(f"{i}. {item['name']} - {item['url']}")
#         print("=" * 50 + "\n")
#
#     except Exception as e:
#         logger.error(f"💥 Ошибка в main: {str(e)}")
#     finally:
#         logger.info("🛑 Завершение работы парсера")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())






