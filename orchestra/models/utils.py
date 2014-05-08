from django.conf import settings
from django.db.models import loading, Manager
from django.utils import importlib


def get_model(label, import_module=True):
    """ returns the modeladmin registred for model """
    app_label, model_name = label.split('.')
    model = loading.get_model(app_label, model_name)
    if model is None:
        # Sometimes the models module is not yet imported
        for app in settings.INSTALLED_APPS:
            if app.endswith(app_label):
                app_label = app
        importlib.import_module('%s.%s' % (app_label, 'admin'))
        return loading.get_model(*label.split('.'))
    return model


def queryset_as_manager(qs_class):
    # Allow chained managers
    # Based on http://djangosnippets.org/snippets/562/#c2486
    class ChainerManager(Manager):
        def __init__(self):
            super(ChainerManager,self).__init__()
            self.queryset_class = qs_class
        
        def get_query_set(self):
            return self.queryset_class(self.model)
        
        def __getattr__(self, attr, *args):
            try:
                return getattr(type(self), attr, *args)
            except AttributeError:
                return getattr(self.get_query_set(), attr, *args)
    return ChainerManager()


def get_field_value(obj, field_name):
    names = field_name.split('__')
    rel = getattr(obj, names.pop(0))
    for name in names:
        try:
            rel = getattr(rel, name)
        except AttributeError:
            # maybe it is a query manager
            rel = getattr(rel.get(), name)
    return rel

