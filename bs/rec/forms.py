from .models import Gldetail, Entity, Period, Status
from django.forms import ModelForm, inlineformset_factory
from .models import Gldetail, Glpost, Entity, Period
# from django.core.files.storage import FileSystemStorage
from crispy_forms.helper import FormHelper
from django import forms
from django.forms import widgets
from django.contrib.auth.models import User
from django.shortcuts import render


class GldetailViewForm(forms.ModelForm):

    entity = forms.ModelChoiceField(queryset=Entity.objects.all(), to_field_name='entity', empty_label="Select Entity")
    period = forms.ModelChoiceField(queryset=Period.objects.all(), to_field_name='period')


    class Meta:
        model = Gldetail
        fields = ['entity', 'period']

    def __init__(self, user, *args, **kwargs):
        super(GldetailViewForm, self).__init__(*args, **kwargs)
        if user.is_active:
            self.fields['entity'].queryset = Entity.objects.filter(users=user)

class StatusViewForm(forms.ModelForm):
    period = forms.ModelChoiceField(
        queryset=Period.objects.all(),
        to_field_name='period',
        label='Period',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label='User',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    entity = forms.ModelChoiceField(
        queryset=Entity.objects.all(),
        label='Entity',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Gldetail
        fields = ('period', 'user', 'entity')

    def __init__(self, *args, **kwargs):
        super(StatusViewForm, self).__init__(*args, **kwargs)
        # Optional: Order fields or customize initial values
        self.fields['period'].empty_label = "Select Period"
        self.fields['user'].empty_label = "All Users"
        self.fields['entity'].empty_label = "All Entities"


class GldetailForm(forms.ModelForm):
    entity = forms.ModelChoiceField(
        queryset=Entity.objects.all(),
        empty_label="Select Entity",
        widget=forms.Select(attrs={
            'class': 'form-select shadow-sm',
            'style': 'width: 100%; max-width: 400px;',
        })
    )
    period = forms.ModelChoiceField(
        queryset=Period.objects.all(),
        empty_label="Select Period",
        widget=forms.Select(attrs={
            'class': 'form-select shadow-sm',
            'style': 'width: 100%; max-width: 400px;',
        })
    )
    status = forms.ModelChoiceField(
        queryset=Status.objects.all(),
        empty_label="Select Status",
        widget=forms.Select(attrs={
            'class': 'form-select shadow-sm',
            'style': 'width: 100%; max-width: 400px;',
        })
    )

    class Meta:
        model = Gldetail
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(GldetailForm, self).__init__(*args, **kwargs)

        # Optional styling for the name and amount fields
        self.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter GL detail name',
            'style': 'width: 100%; max-width: 400px;',
        })
        self.fields['amount'].widget.attrs.update({
            'class': 'form-control text-end',
            'placeholder': '0.00',
            'style': 'width: 100%; max-width: 300px;',
        })


class ReadonlyWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        if value is not None:
            try:
                # Fetch the User object using the ID
                user = User.objects.get(pk=value)
                return user.username
            except User.DoesNotExist:
                return "-"  # Return "-" if the user doesn't exist
        return "-"  # Return "-" if value is None


class GlpostForm(forms.ModelForm):
    created_by_display = forms.CharField(
        required=False, disabled=True, widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )
    updated_by_display = forms.CharField(
        required=False, disabled=True, widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )

    class Meta:
        model = Glpost
        exclude = ("entry_type", "created_at",
                   "updated_at", "created_by", "updated_by")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(GlpostForm, self).__init__(*args, **kwargs)

        # Set display fields
        self.fields['created_by_display'].initial = (
            self.instance.created_by.username if self.instance.created_by else "-"
        )
        self.fields['updated_by_display'].initial = (
            self.instance.updated_by.username if self.instance.updated_by else "-"
        )

        # Existing field customizations
        self.fields['jdate'].widget.attrs['style'] = "width: 110px"
        self.fields['jdate'].widget.attrs['placeholder'] = "mm/dd/yyyy"
        self.fields['jdate'].widget.attrs['minlength'] = "10"
        self.fields['jref'].widget.attrs['style'] = "width: 80px"
        self.fields['jref'].widget.attrs['placeholder'] = "123456"
        self.fields['jref'].widget.attrs['minlength'] = "6"
        self.fields['jamt'].widget.attrs['style'] = "width: 140px"
        self.fields['jamt'].widget.attrs['class'] = "text-right"
        self.fields['jdesc'].widget.attrs['style'] = "width: 200px"
        self.fields['jdesc'].widget.attrs['minlength'] = "2"

    def save(self, commit=True):
        instance = super(GlpostForm, self).save(commit=False)
        if not instance.pk and self.user:
            instance.created_by = self.user
        if self.user:
            instance.updated_by = self.user
        if commit:
            instance.save()
        return instance
GlpostFormSet = inlineformset_factory(Gldetail, Glpost, form=GlpostForm, extra=1)


class GldetailForm(forms.ModelForm):
    class Meta:
        model = Gldetail
        fields = ['entity', 'period', 'glnum', 'gldesc', 'glamt', 'status']
        widgets = {
            'glnum': forms.TextInput(attrs={'placeholder': 'GL Number'}),
            'gldesc': forms.TextInput(attrs={'placeholder': 'GL Description'}),
            'glamt': forms.NumberInput(attrs={'step': '0.01'}),
        }


class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = ['entity', 'users']
        widgets = {
            'entity': forms.TextInput(attrs={'placeholder': 'Entity Name'}),
            'users': forms.SelectMultiple()
        }


class PeriodForm(forms.ModelForm):
    class Meta:
        model = Period
        fields = ['period']
        widgets = {
            'period': forms.TextInput(attrs={'placeholder': 'Period Format e.g., 2024-Q1'}),
        }


class StatusForm(forms.ModelForm):
    class Meta:
        model = Status
        fields = ['option']
        widgets = {
            'option': forms.TextInput(attrs={'placeholder': 'Status Option'}),
        }
