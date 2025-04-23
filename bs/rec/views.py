# Django core imports
from datetime import datetime
from django.urls import reverse
from .models import Gldetail, Glpost
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import letter
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from django.db import transaction
from django.db.models import Q, Count, Sum, F, Case, When
from django.db.models.functions import Coalesce
from PIL import Image as PILImage
import qrcode

# Django generic views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django_filters.views import FilterView

# Third-party imports
from tablib import Dataset
import tablib
from io import BytesIO
from decimal import Decimal
import itertools

# ReportLab for PDF generation
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

# Local app models and forms
from .models import (
    Entity, Period, Status, Gldetail, GlReconciliation, Glpost, User
)
from .forms import (
    EntityForm, PeriodForm, StatusForm, GldetailForm, GldetailViewForm,
    StatusViewForm, GlpostFormSet
)
from .resources import GldetailResource
from django.contrib import messages
from django.contrib.messages import success, error, info, warning






# Create your views here.
def import_data(request):
    if request.method == 'POST':
        gldetail_resource = GldetailResource()
        dataset = Dataset()
        new_gldetails = request.FILES['myfile']

        imported_data = dataset.load(new_gldetails.read().decode('utf-8'), format='csv')
        result = gldetail_resource.import_data(dataset, dry_run=True)  # Test the data import

        if result.has_errors():
            messages.success(request, 'Import file contains errors!')
        else:
            gldetail_resource.import_data(dataset, dry_run=False)  # Actually import now
            messages.success(request, 'Import file uploaded successfully!')
     
    return render(request, 'rec/gldetail_import.html')


class GldetailView(View):

    def get(self, request):
        form = GldetailViewForm(request.user)
        summary = self.get_summary_data()
        return render(request, "rec/gldetail_list.html", {
            'form': form,
            **summary  # include summary info for all status, entities, and periods
        })

    def post(self, request):
        form = GldetailViewForm(request.user, request.POST)
        entities = periods = gldetails = None

        if form.is_valid():
            try:
                selected_entity = Entity.objects.get(
                    entity=form.cleaned_data['entity'])
                selected_period = Period.objects.get(
                    period=form.cleaned_data['period'])

                post_field_name = Glpost._meta.get_field(
                    'gldetail').related_query_name()
                field_ref = f"{post_field_name}__jamt"

                gldetails = Gldetail.objects.filter(
                    entity=selected_entity,
                    period=selected_period,
                    entity__users=request.user
                ).annotate(total_sales=Coalesce(Sum(field_ref), 0))

                entities = selected_entity
                periods = selected_period

            except (Entity.DoesNotExist, Period.DoesNotExist):
                pass  # optionally handle errors here

        summary = self.get_summary_data()

        return render(request, "rec/gldetail_list.html", {
            'form': form,
            'entities': entities,
            'periods': periods,
            'gldetails': gldetails,
            **summary  # still include the summary info
        })

    def get_summary_data(self):
        # ✅ Summary info not dependent on form filters
        status_summary = Status.objects.all().annotate(
            total_amount=Coalesce(Sum('gldetail__glamt'), 0),
            total_count=Coalesce(Sum('gldetail__id'), 0)
        )

        entity_summary = Entity.objects.all().annotate(
            total_amount=Coalesce(Sum('gldetail__glamt'), 0),
            total_count=Coalesce(Sum('gldetail__id'), 0)
        )

        period_summary = Period.objects.all().annotate(
            total_amount=Coalesce(Sum('gldetail__glamt'), 0),
            total_count=Coalesce(Sum('gldetail__id'), 0)
        )

        return {
            'status_summary': status_summary,
            'entity_summary': entity_summary,
            'period_summary': period_summary,
        }





class StatusView(View):

    def get(self, request):
        form = StatusViewForm()
        return render(request, "rec/status.html", {'form': form})

    def post(self, request):
        form = StatusViewForm(request.POST)
        periods = None
        status_summary = None
        reconciliations = None

        if form.is_valid():
            periods = form.cleaned_data['period']
            selected_user = form.cleaned_data['user']
            selected_entity = form.cleaned_data['entity']

            # Filter GL details based on selected filters
            gldetails = Gldetail.objects.filter(
                period=periods,
                entity=selected_entity,
                entity__users=selected_user
            )

            # Loop through each GL and auto-reconcile
            for gldetail in gldetails:
                beginning_balance = gldetail.glamt or Decimal('0.00')
                posts = Glpost.objects.filter(gldetail=gldetail)
                total_posted = posts.aggregate(total=Coalesce(
                    Sum('jamt'), Decimal('0.00')))['total']

                ending_balance = beginning_balance + total_posted
                status_text = "Reconciled" if ending_balance == beginning_balance else "Difference"
                status_obj, _ = Status.objects.get_or_create(
                    option=status_text)

                # Update the Gldetail status
                gldetail.status = status_obj
                gldetail.save()

                # Create or update reconciliation
                GlReconciliation.objects.update_or_create(
                    gldetail=gldetail,
                    defaults={
                        'beginning_balance': beginning_balance,
                        'ending_balance': ending_balance,
                        'adjustments': total_posted,
                        'explanation': f'Auto reconciled by system on {now().date()}',
                        'prepared_by': request.user,
                        'status': status_obj,
                    }
                )

            # Summary count by status for the selected filters
            status_summary = Gldetail.objects.filter(
                period=periods,
                entity=selected_entity,
                entity__users=selected_user
            ).values("entity__entity").annotate(
                count_pending=Count(
                    Case(When(status__option="Pending", then=1))),
                count_inprogress=Count(
                    Case(When(status__option="In Progress", then=1))),
                count_completed=Count(
                    Case(When(status__option="Completed", then=1))),
                count_reconciled=Count(
                    Case(When(status__option="Reconciled", then=1))),
                count_difference=Count(
                    Case(When(status__option="Difference", then=1))),
            ).order_by("entity")

            reconciliations = GlReconciliation.objects.filter(
                gldetail__period=periods,
                gldetail__entity=selected_entity,
                prepared_by=request.user
            ).select_related('gldetail', 'status')

            messages.success(
                request, "Reconciliation completed and status updated for all GL accounts.")

        context = {
            'form': form,
            'periods': periods,
            'status': status_summary,
            'reconciliations': reconciliations,
        }

        return render(request, "rec/status.html", context)

class GldetailCreate(CreateView):
    model = Gldetail
    fields = ['entity', 'period', 'glnum', 'gldesc', 'glamt']


class GldetailGlpostCreate(LoginRequiredMixin, CreateView):
    model = Gldetail
    form_class = GldetailForm
    success_url = reverse_lazy('gldetail-list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['glposts'] = GlpostFormSet(
                self.request.POST, self.request.FILES, form_kwargs={
                    'user': self.request.user}
            )
        else:
            data['glposts'] = GlpostFormSet(
                form_kwargs={'user': self.request.user})
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        glposts = context['glposts']
        with transaction.atomic():
            # Set created_by and updated_by for the Gldetail instance
            form.instance.created_by = self.request.user
            form.instance.updated_by = self.request.user
            self.object = form.save()

            # Process the glpost formset
            if glposts.is_valid():
                glposts.instance = self.object
                glpost_objs = glposts.save(commit=False)
                for gl in glpost_objs:
                    # Set created_by and updated_by for each Glpost
                    gl.created_by = self.request.user
                    gl.updated_by = self.request.user
                    gl.save()
                glposts.save_m2m()  # Save any many-to-many relationships if applicable

        return super().form_valid(form)


class GldetailPDFView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        # Fetch the Gldetail object
        gldetail = get_object_or_404(Gldetail, pk=pk)

        # Prepare the HTTP response with PDF content type
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="gldetail_{gldetail.glnum}.pdf"'

        # Create the PDF document
        doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=0.5*inch,
                                leftMargin=0.5*inch, topMargin=0.75*inch, bottomMargin=0.5*inch)
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name='TitleStyle',
            parent=styles['Title'],
            fontSize=16,
            spaceAfter=12,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            name='HeadingStyle',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            name='NormalStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4
        )
        signature_style = ParagraphStyle(
            name='SignatureStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceBefore=12,
            spaceAfter=4,
            alignment=0  # Left
        )

        # Header
        elements.append(Paragraph("General Ledger Detail Report", title_style))
        elements.append(Spacer(1, 0.2*inch))

        # Gldetail Information
        elements.append(Paragraph("GL Detail Information", heading_style))
        elements.append(
            Paragraph(f"<b>GL Number:</b> {gldetail.glnum}", normal_style))
        elements.append(
            Paragraph(f"<b>Description:</b> {gldetail.gldesc}", normal_style))
        elements.append(Paragraph(
            # RWF, no decimals
            f"<b>Amount:</b> RWF {int(gldetail.glamt):,}", normal_style))
        elements.append(
            Paragraph(f"<b>Entity:</b> {gldetail.entity or '-'}", normal_style))
        elements.append(
            Paragraph(f"<b>Period:</b> {gldetail.period or '-'}", normal_style))
        elements.append(
            Paragraph(f"<b>Status:</b> {gldetail.status or '-'}", normal_style))
        elements.append(Paragraph(
            f"<b>Created By:</b> {gldetail.created_by.username if gldetail.created_by else '-'}", normal_style))
        elements.append(Paragraph(
            f"<b>Updated By:</b> {gldetail.updated_by.username if gldetail.updated_by else '-'}", normal_style))
        elements.append(Paragraph(
            f"<b>Last Updated:</b> {gldetail.updated_at.strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
        elements.append(Spacer(1, 0.2*inch))

        # Glpost Table
        elements.append(Paragraph("Related GL Posts", heading_style))
        data = [['Date', 'Reference', 'Amount',
                 'Description', 'Created By', 'Updated By']]
        glposts = gldetail.glpost_set.all()  # Fetch related Glpost entries
        for glpost in glposts:
            data.append([
                glpost.jdate,
                glpost.jref,
                f"RWF {int(glpost.jamt):,}",  # RWF, no decimals
                glpost.jdesc,
                glpost.created_by.username if glpost.created_by else '-',
                glpost.updated_by.username if glpost.updated_by else '-'
            ])

        # Create table
        table = Table(data, colWidths=[
                      1.0*inch, 1.0*inch, 1.2*inch, 1.5*inch, 1.0*inch, 1.0*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))

        # Signature Section
        full_name = gldetail.created_by.get_full_name()
        display_name = full_name if full_name.strip() else gldetail.created_by.username
        # Signature Section

        elements.append(
            Paragraph(
                f"<b>Prepared and Downloaded by:</b> {display_name}", styles['Normal']
            )
        )
        elements.append(
        Paragraph(f"<i>Signed by: ______________________</i>",
                  styles['Normal'])
        )
        elements.append(Paragraph(
            f"<b>Date:</b> {gldetail.updated_at.strftime('%Y-%m-%d')}", normal_style))
        # Placeholder for signature
        elements.append(Paragraph("Signature & Stamp: ", signature_style))
        elements.append(Spacer(1, 0.2*inch))

        # Footer
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.drawString(0.5*inch, 0.3*inch, f"Page {doc.page}")
            canvas.drawRightString(
                doc.pagesize[0] - 0.5*inch, 0.3*inch, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            canvas.restoreState()

        # Build the PDF
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)

        return response


class PostMixin(LoginRequiredMixin):
    def form_valid(self, form):
        form.instance.username = self.request.user
        return super().form_valid(form)


class GldetailGlpostUpdate(LoginRequiredMixin, UpdateView):
    model = Gldetail
    form_class = GldetailForm
    success_url = reverse_lazy('gldetail-list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['glposts'] = GlpostFormSet(
                self.request.POST, self.request.FILES, instance=self.object)
        else:
            data['glposts'] = GlpostFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        glposts = context['glposts']
        with transaction.atomic():
            # Update main object’s updated_by field
            form.instance.updated_by = self.request.user
            self.object = form.save()

            if glposts.is_valid():
                glposts.instance = self.object
                glpost_objs = glposts.save(commit=False)

                # Save or update each entry in the formset
                for gl in glpost_objs:
                    if not gl.pk:  # new object
                        gl.created_by = self.request.user
                    gl.updated_by = self.request.user
                    gl.save()

                # Handle deletions
                for obj in glposts.deleted_objects:
                    obj.delete()

        return super().form_valid(form)
class GldetailDelete(DeleteView):
    model = Gldetail
    success_url = reverse_lazy('gldetail-list')

def password_success(request):
    return render(request, 'rec/password_success.html', {})


@login_required
def export_reconciliations_excel(request):
    period_id = request.GET.get('period')
    period = Period.objects.get(id=period_id)
    reconciliations = GlReconciliation.objects.filter(
        gldetail__period=period, prepared_by=request.user
    ).select_related('gldetail', 'status')

    dataset = Dataset()
    dataset.headers = [
        'GL Number', 'Description', 'Beginning Balance',
        'Adjustments', 'Ending Balance', 'Status', 'Prepared By'
    ]

    for rec in reconciliations:
        dataset.append([
            rec.gldetail.glnum,
            rec.gldetail.gldesc,
            float(rec.beginning_balance),
            float(rec.adjustments),
            float(rec.ending_balance),
            rec.status.option,
            rec.prepared_by.username
        ])

    response = HttpResponse(dataset.export(
        'xlsx'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="reconciliation_{period.period}.xlsx"'
    return response


@login_required
def export_reconciliations_pdf(request):
    # Fetch parameters
    period_id = request.GET.get('period')
    user_id = request.GET.get('user')

    # Fetch objects
    period = get_object_or_404(Period, id=period_id)
    selected_user = get_object_or_404(User, id=user_id)

    # Query reconciliations
    reconciliations = GlReconciliation.objects.filter(
        gldetail__period=period,
        prepared_by=selected_user
    ).select_related('gldetail', 'status')

    # Set up response and PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reconciliation_{period.period}.pdf"'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.5*inch
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=12,
        alignment=1  # Center
    )
    heading_style = ParagraphStyle(
        name='HeadingStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=6
    )
    normal_style = ParagraphStyle(
        name='NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4
    )
    signature_style = ParagraphStyle(
        name='SignatureStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=12,
        spaceAfter=4,
        alignment=0  # Left
    )

    elements = []

    # Generate QR code
    qr_url = request.build_absolute_uri(
        reverse('status') +
        f'?period={period_id}&user={user_id}'
    )  # Adjust to your verification URL
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Save QR code to BytesIO
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Header
    elements.append(
        Paragraph("Balance Sheet Reconciliation Report", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Report Information
    elements.append(Paragraph("Report Details", heading_style))
    elements.append(Paragraph(f"<b>Period:</b> {period.period}", normal_style))
    elements.append(Paragraph(
        f"<b>Prepared By:</b> {selected_user.get_full_name() or selected_user.username}", normal_style))
    elements.append(Spacer(1, 0.2*inch))

    # Table data
    elements.append(Paragraph("Reconciliations", heading_style))
    table_data = [['GL Number', 'Description',
                   'Begin Bal.', 'Adjustments', 'End Bal.', 'Status']]
    for rec in reconciliations:
        table_data.append([
            rec.gldetail.glnum,
            rec.gldetail.gldesc,
            f"RWF {int(rec.beginning_balance):,}",
            f"RWF {int(rec.adjustments):,}",
            f"RWF {int(rec.ending_balance):,}",
            rec.status.option if rec.status else '-'
        ])

    # Create table
    table = Table(table_data, colWidths=[
                  1.0*inch, 1.8*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Approval Section
    elements.append(Paragraph("Approval", heading_style))
    display_name = selected_user.get_full_name() or selected_user.username
    elements.append(
        Paragraph(f"<b>Prepared By:</b> {display_name}", normal_style))
    elements.append(
        Paragraph(f"<b>Signed By:</b> {display_name}", normal_style))
    elements.append(
        Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}", normal_style))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Scan to Verify", normal_style))
    elements.append(Image(qr_buffer, width=1*inch, height=1*inch))
    elements.append(Spacer(1, 0.2*inch))

    # Footer
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(0.5*inch, 0.3*inch, f"Page {doc.page}")
        canvas.drawRightString(doc.pagesize[0] - 0.5*inch, 0.3*inch,
                               f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        canvas.restoreState()

    # Build PDF
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response
# admin


# Mixin to restrict access to the owner of the object
class OwnerOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.username != request.user:
            return HttpResponseForbidden("You are not allowed to modify this record.")
        return super().dispatch(request, *args, **kwargs)


# ---------------------------
# GLDETAIL VIEWS
# ---------------------------
@method_decorator(login_required, name='dispatch')
class GldetailListView(ListView):
    model = Gldetail
    template_name = 'reconciliations/gldetail_list.html'
    context_object_name = 'gldetails'

    def get_queryset(self):
        return Gldetail.objects.filter(username=self.request.user)


@method_decorator(login_required, name='dispatch')
class GldetailCreateView(CreateView):
    model = Gldetail
    form_class = GldetailForm
    template_name = 'reconciliations/gldetail_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['entities'] = Entity.objects.all()
        context['periods'] = Period.objects.all()
        context['statuses'] = Status.objects.all()
        return context

    def form_valid(self, form):
        user = self.request.user
        form.instance.username = user           # ✅ Last updated by
        form.instance.created_by = user         # ✅ Original creator
        return super().form_valid(form)



@method_decorator(login_required, name='dispatch')
class GldetailUpdateView(OwnerOnlyMixin, UpdateView):
    model = Gldetail
    fields = ['entity', 'period', 'glnum', 'gldesc', 'glamt', 'status']
    template_name = 'reconciliations/gldetail_form.html'
    success_url = reverse_lazy('gldetail-list')


@method_decorator(login_required, name='dispatch')
class GldetailDeleteView(OwnerOnlyMixin, DeleteView):
    model = Gldetail
    template_name = 'reconciliations/gldetail_confirm_delete.html'
    success_url = reverse_lazy('gldetail-list')


# ---------------------------
# ENTITY VIEWS
# ---------------------------
@method_decorator(login_required, name='dispatch')
class EntityListView(ListView):
    model = Entity
    template_name = 'reconciliations/entity_list.html'
    context_object_name = 'entities'


@method_decorator(login_required, name='dispatch')
class EntityCreateView(CreateView):
    model = Entity
    fields = ['entity', 'users']
    template_name = 'reconciliations/entity_form.html'
    success_url = reverse_lazy('entity-list')


@method_decorator(login_required, name='dispatch')
class EntityUpdateView(UpdateView):
    model = Entity
    fields = ['entity', 'users']
    template_name = 'reconciliations/entity_form.html'
    success_url = reverse_lazy('entity-list')


@method_decorator(login_required, name='dispatch')
class EntityDeleteView(DeleteView):
    model = Entity
    template_name = 'reconciliations/entity_confirm_delete.html'
    success_url = reverse_lazy('entity-list')


# ---------------------------
# PERIOD VIEWS
# ---------------------------
@method_decorator(login_required, name='dispatch')
class PeriodListView(ListView):
    model = Period
    template_name = 'reconciliations/period_list.html'
    context_object_name = 'periods'


@method_decorator(login_required, name='dispatch')
class PeriodCreateView(CreateView):
    model = Period
    fields = ['period']
    template_name = 'reconciliations/period_form.html'
    success_url = reverse_lazy('period-list')


@method_decorator(login_required, name='dispatch')
class PeriodUpdateView(UpdateView):
    model = Period
    fields = ['period']
    template_name = 'reconciliations/period_form.html'
    success_url = reverse_lazy('period-list')


@method_decorator(login_required, name='dispatch')
class PeriodDeleteView(DeleteView):
    model = Period
    template_name = 'reconciliations/period_confirm_delete.html'
    success_url = reverse_lazy('period-list')


# ---------------------------
# STATUS VIEWS
# ---------------------------
@method_decorator(login_required, name='dispatch')
class StatusListView(ListView):
    model = Status
    template_name = 'reconciliations/status_list.html'
    context_object_name = 'statuses'


@method_decorator(login_required, name='dispatch')
class StatusCreateView(CreateView):
    model = Status
    fields = ['option']
    template_name = 'reconciliations/status_form.html'
    success_url = reverse_lazy('status-lists')


@method_decorator(login_required, name='dispatch')
class StatusUpdateView(UpdateView):
    model = Status
    fields = ['option']
    template_name = 'reconciliations/status_form.html'
    success_url = reverse_lazy('status-lists')


@method_decorator(login_required, name='dispatch')
class StatusDeleteView(DeleteView):
    model = Status
    template_name = 'reconciliations/status_confirm_delete.html'
    context_object_name = 'status'
    # Redirect to status list on successful deletion
    success_url = reverse_lazy('status-lists')

    def get_object(self, queryset=None):
        # Get the status object to delete based on the pk from the URL
        return get_object_or_404(Status, pk=self.kwargs['pk'])
