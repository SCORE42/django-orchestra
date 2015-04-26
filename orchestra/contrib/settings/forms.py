import math
from copy import deepcopy
from functools import partial

from django import forms
from django.core.exceptions import ValidationError
from django.forms.formsets import formset_factory
from django.utils.translation import ugettext_lazy as _

from orchestra.forms import ReadOnlyFormMixin, widgets

from . import parser

from django import forms
from django.utils.safestring import mark_safe


class SettingForm(ReadOnlyFormMixin, forms.Form):
    TEXTAREA = partial(forms.CharField,
        widget=forms.Textarea(attrs={
            'cols': 65,
            'rows': 2,
            'style': 'font-family:monospace'
        }))
    CHARFIELD = partial(forms.CharField,
                widget=forms.TextInput(attrs={
                    'size': 65,
                    'style': 'font-family:monospace'
                }))
    NON_EDITABLE = partial(forms.CharField, widget=widgets.ShowTextWidget(), required=False)
    FORMFIELD_FOR_SETTING_TYPE = {
            bool: partial(forms.BooleanField, required=False),
            int: forms.IntegerField,
            tuple: TEXTAREA,
            list: TEXTAREA,
            dict: TEXTAREA,
            type(_()): CHARFIELD,
            str: CHARFIELD,
        }
    
    name = forms.CharField(label=_("name"))
    default = forms.CharField(label=_("default"))
    
    class Meta:
        readonly_fields = ('name', 'default')
    
    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        if initial:
            self.setting_type = initial['type']
            serialized_value = parser.serialize(initial['value'])
            serialized_default = parser.serialize(initial['default'])
            if not initial['editable'] or isinstance(serialized_value, parser.NotSupported):
                field = self.NON_EDITABLE
            else:
                choices = initial.get('choices')
                field = forms.ChoiceField
                multiple = initial['multiple']
                if multiple:
                    field = partial(forms.MultipleChoiceField, widget=forms.CheckboxSelectMultiple)
                if choices:
                    # Lazy loading
                    if callable(choices):
                        choices = choices()
                    if not multiple:
                        choices = tuple((parser.serialize(val), verb) for val, verb in choices)
                    field = partial(field, choices=choices)
                else:
                    field = self.FORMFIELD_FOR_SETTING_TYPE.get(self.setting_type, self.NON_EDITABLE)
                    field = deepcopy(field)
            value = initial['value']
            default = initial['default']
            real_field = field
            while isinstance(real_field, partial):
                real_field = real_field.func
            # Do not serialize following form types
            if real_field not in (forms.MultipleChoiceField, forms.BooleanField):
                value = serialized_value
            if real_field is not forms.BooleanField:
                default = serialized_default
            initial['value'] = value
            initial['default'] = default
        super(SettingForm, self).__init__(*args, **kwargs)
        if initial:
            self.changed = bool(value != default)
            self.fields['value'] = field(label=_("value"))
            if isinstance(self.fields['value'].widget, forms.Textarea):
                rows = math.ceil(len(value)/65)
                self.fields['value'].widget.attrs['rows'] = rows
            self.fields['name'].help_text = initial['help_text']
            self.fields['name'].widget.attrs['readonly'] = True
            self.app = initial['app']
        
    def clean_value(self):
        value = self.cleaned_data['value']
        if not value:
            return parser.NotSupported()
        if not isinstance(value, str):
            value = parser.serialize(value)
        try:
            value = eval(value, parser.get_eval_context())
        except Exception as exc:
            raise ValidationError(str(exc))
        if not isinstance(value, self.setting_type):
            if self.setting_type in (tuple, list) and isinstance(value, (tuple, list)):
                value = self.setting_type(value)
            else:
                raise ValidationError("Please provide a %s." % self.setting_type.__name__)
        return value


SettingFormSet = formset_factory(SettingForm, extra=0)