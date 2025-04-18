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
import aiohttp


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


# ... (импорты остаются те же)

class ParserTimer:
    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.info("⏱ Начало парсинга")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time
        logger.info(f"⏱ Время выполнения: {self.elapsed:.2f} сек")


async def get_product_data(context, url: str, semaphore: asyncio.Semaphore) -> Optional[dict]:
    async with semaphore:
        page = None
        try:
            page = await context.new_page()
            await page.route('**/*.{png,jpg,jpeg,webp,svg,gif,css,woff2}', lambda route: route.abort())

            # Быстрая проверка доступности страницы
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            if not response or response.status >= 400:
                raise Exception(f"HTTP {getattr(response, 'status', 'NO_RESPONSE')}")

            # Ждём либо изображение, либо таймаут
            await asyncio.wait_for(
                page.wait_for_selector('img[itemprop="image"]', timeout=10_000),
                timeout=10_000
            )

            product_data = await page.evaluate('''() => {
                const nameEl = document.querySelector('h1[itemprop="name"]');
                if (!nameEl) return null;

                const imgEl = document.querySelector('img[itemprop="image"]');
                const imgSrc = imgEl?.src || imgEl?.getAttribute('data-src') || '';

                return {
                    name: nameEl.textContent.trim(),
                    url: window.location.href,
                    image: imgSrc
                };
            }''')

            if product_data:
                logger.debug(f"Успешно: {product_data['name'][:30]}...")
                return product_data
            return None

        except Exception as e:
            logger.debug(f"Ошибка ({url[-15:]}): {str(e)[:50]}...")
            return None
        finally:
            if page:
                await page.close()


async def parse_products_page(page_num: int, items_limit: int = None):
    with ParserTimer():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 720}
            )

            try:
                main_page = await context.new_page()
                product_links = await get_product_links(main_page, page_num)
                if items_limit:
                    product_links = product_links[:items_limit]

                semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
                tasks = [get_product_data(context, link, semaphore) for link in product_links]

                results = []
                for future in tqdm.as_completed(tasks, desc="Обработка товаров"):
                    result = await future
                    if result:
                        results.append(result)

                logger.info(f"📊 Результатов: {len(results)}/{len(product_links)}")
                return results

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




# async def download_single_image(session: aiohttp.ClientSession, url: str, filename: str):
#     """
#     Загрузка одного изображения
#     """
#     try:
#         async with session.get(url) as response:
#             if response.status == 200:
#                 async with aiofiles.open(filename, mode='wb') as f:
#                     await f.write(await response.read())
#                 return filename
#     except Exception as e:
#         logger.warning(f"Не удалось загрузить {url}: {str(e)[:50]}")
#         return None


# Модифицируем функцию cli_main
async def cli_main(args):
    setup_logging(args.log_file)

    try:
        logger.info(f"🚀 Запуск парсера: страница {args.page}, лимит {args.limit}")
        results = await parse_products_page(page_num=args.page, items_limit=args.limit)

        # Массовая загрузка изображений
        if results and args.download_images:
            image_urls = [item['image'] for item in results if item.get('image')]
            logger.info(f"🖼️ Начало загрузки {len(image_urls)} изображений...")
            downloaded = await bulk_download_images(image_urls)
            logger.info(f"✅ Загружено {len(downloaded)} изображений")

        # Вывод результатов
        print("\n" + "=" * 50)
        print(f"Всего получено {len(results)} результатов:")
        for i, item in enumerate(results[:5], 1):
            print(f"{i}. {item['name'][:50]}... - {item['url']}")
        if len(results) > 5:
            print(f"... и еще {len(results) - 5} товаров")

        return 0

    except Exception as e:
        logger.error(f"💥 Ошибка: {str(e)}", exc_info=True)
        return 1


# Обновляем аргументы командной строки
def parse_cli_args():
    parser = argparse.ArgumentParser(
        description="🕵️ Парсер сайта lombard-perspectiva.ru",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--page', type=int, default=1, help='Номер страницы каталога')
    parser.add_argument('--limit', type=int, default=None, help='Максимальное количество товаров для парсинга')
    parser.add_argument('--log-file', type=str, default=None, help='Файл для сохранения логов')
    parser.add_argument('--download-images', action='store_true', help='Загружать изображения товаров')
    return parser.parse_args()

if __name__ == "__main__":
    setup_logging()
    args = parse_cli_args()
    sys.exit(asyncio.run(cli_main(args)))
