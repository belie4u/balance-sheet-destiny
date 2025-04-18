from django.urls import path
from .import views

#--- ADDED THIS SECTION TO UPLOAD PHOTOS !!!! ---
from django.conf.urls.static import static
from django.conf import settings

from django.conf.urls import url
from .models import Gldetail

from .views import (
    GldetailListView, GldetailCreateView, GldetailUpdateView, GldetailDeleteView,
    EntityListView, EntityCreateView, EntityUpdateView, EntityDeleteView,
    PeriodListView, PeriodCreateView, PeriodUpdateView, PeriodDeleteView,
    StatusListView, StatusCreateView, StatusUpdateView, StatusDeleteView, GldetailPDFView
)
#------------------------------------------------

urlpatterns = [
    path('import', views.import_data, name='gldetail-import'),
    path('', views.GldetailView.as_view(), name='gldetail-list'),
    path('status', views.StatusView.as_view(), name='status'),
    path('gldetail/add/', views.GldetailGlpostCreate.as_view(), name='gldetail-add'),
    path('gldetail/<int:pk>', views.GldetailGlpostUpdate.as_view(), name='gldetail-update'),
    path('gldetail/<int:pk>', views.GldetailDelete.as_view(), name='gldetail-delete'),
    path('export/reconciliations/excel/', views.export_reconciliations_excel,
         name='export-reconciliations-excel'),
    path('export/reconciliations/pdf/', views.export_reconciliations_pdf,
         name='export-reconciliations-pdf'),


    # ---------------------------
    # GLDETAIL URLs
    # ---------------------------
    path('gldetails/', GldetailListView.as_view(), name='gldetail-lists'),
    path('gldetails/create/', GldetailCreateView.as_view(), name='gldetail-create'),
    path('gldetails/<int:pk>/update/',
         GldetailUpdateView.as_view(), name='gldetail-update'),
    path('gldetails/<int:pk>/delete/',
         GldetailDeleteView.as_view(), name='gldetail-delete'),

    # ---------------------------
    # ENTITY URLs
    # ---------------------------
    path('entities/', EntityListView.as_view(), name='entity-list'),
    path('entities/create/', EntityCreateView.as_view(), name='entity-create'),
    path('entities/<int:pk>/update/',
         EntityUpdateView.as_view(), name='entity-update'),
    path('entities/<int:pk>/delete/',
         EntityDeleteView.as_view(), name='entity-delete'),

    # ---------------------------
    # PERIOD URLs
    # ---------------------------
    path('periods/', PeriodListView.as_view(), name='period-list'),
    path('periods/create/', PeriodCreateView.as_view(), name='period-create'),
    path('periods/<int:pk>/update/',
         PeriodUpdateView.as_view(), name='period-update'),
    path('periods/<int:pk>/delete/',
         PeriodDeleteView.as_view(), name='period-delete'),

    # ---------------------------
    # STATUS URLs
    # ---------------------------
    path('statuses/', StatusListView.as_view(), name='status-lists'),
    path('statuses/create/', StatusCreateView.as_view(), name='status-create'),
    path('statuses/<int:pk>/update/',
         StatusUpdateView.as_view(), name='status-update'),
    path('statuses/<int:pk>/delete/',
         StatusDeleteView.as_view(), name='status-delete'),


    path('gldetail/<int:pk>/pdf/', GldetailPDFView.as_view(), name='gldetail-pdf'),



]

#--- ADDED THIS SECTION TO UPLOAD PHOTOS !!!! ---
urlpatterns+=static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#