from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from watch.page_parser import parse_products_page
from django.views.generic import ListView, TemplateView
from watch.models import ParsedProduct
from django.utils import timezone

class HomePageView(TemplateView):
    template_name = 'watch/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now()
        return context

class ProductListView(ListView):
    model = ParsedProduct  #.objects.all().order_by('-created_at')
    template_name = 'watch/product_list.html'
    context_object_name = 'products'
    paginate_by = 20

class ParseView(View):
    # Указываем относительный путь к шаблону (правильный способ)
    template_name = 'watch/work_parse.html'

    async def get(self, request):
        # Для Django < 4.1 используем sync_to_async
        return await sync_to_async(render)(request, self.template_name)

    async def post(self, request):
        try:
            if request.headers.get('x-requested-with') != 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Неверный тип запроса'}, status=400)

            page_num = int(request.POST.get('page_num', 1))
            items_limit = int(request.POST.get('items_limit', 0)) or None

            results_raw = await parse_products_page(page_num, items_limit)
            # print("DEBUG:", results_raw)  # Для отладки

            results = []
            for item in results_raw:
                results.append({
                    "name": item.get("name", "Нет имени"),
                    "url": item.get("url", "#"),
                    "img": item.get("img") or item.get("image") or ""  # Фоллбэк
                })

            return JsonResponse({
                'status': 'success',
                'results': results,
                'page_num': page_num,
                'items_count': len(results)
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)