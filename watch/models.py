from django.db import models


class ParsedProduct(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True, null=True)
    product_id = models.CharField(max_length=100, blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)  # поле для фото
    created_at = models.DateTimeField(auto_now_add=True)  # Нужно для сортировки

    def __str__(self):
        return self.title or self.url

