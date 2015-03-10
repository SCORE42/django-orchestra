from orchestra.utils.functional import cached


class Plugin(object):
    verbose_name = None
    # Used on select plugin view
    class_verbose_name = None
    icon = None
    change_readonly_fileds = ()
    
    @classmethod
    def get_name(cls):
        return getattr(cls, 'name', cls.__name__)
    
    @classmethod
    def get_plugins(cls):
        return cls.plugins
    
    @classmethod
    def get_plugin(cls, name):
        if not hasattr(cls, '_registry'):
            cls._registry = {
                plugin.get_name(): plugin for plugin in cls.get_plugins()
            }
        return cls._registry[name]
    
    @classmethod
    def get_verbose_name(cls):
        # don't evaluate p.verbose_name ugettext_lazy
        verbose = getattr(cls.verbose_name, '_proxy____args', [cls.verbose_name])
        if verbose[0]:
            return cls.verbose_name
        else:
            return cls.get_name()
    
    @classmethod
    def get_plugin_choices(cls):
        choices = []
        for plugin in cls.get_plugins():
            verbose = plugin.get_verbose_name()
            choices.append(
                (plugin.get_name(), verbose)
            )
        return sorted(choices, key=lambda e: e[1])
    
    @classmethod
    def get_change_readonly_fileds(cls):
        return cls.change_readonly_fileds


class PluginModelAdapter(Plugin):
    """ Adapter class for using model classes as plugins """
    model = None
    name_field = None
    
    @classmethod
    def get_plugins(cls):
        plugins = []
        for instance in cls.model.objects.filter(is_active=True):
            attributes = {
                'instance': instance,
                'verbose_name': instance.verbose_name
            }
            plugins.append(type('PluginAdapter', (cls,), attributes))
        return plugins
    
    @classmethod
    def get_name(cls):
        return getattr(cls.instance, cls.name_field)


class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not attrs.get('abstract', False):
            if not hasattr(cls, 'plugins'):
                # This branch only executes when processing the mount point itself.
                # So, since this is a new plugin type, not an implementation, this
                # class shouldn't be registered as a plugin. Instead, it sets up a
                # list where plugins can be registered later.
                cls.plugins = []
            else:
                # This must be a plugin implementation, which should be registered.
                # Simply appending it to the list is all that's needed to keep
                # track of it later.
                cls.plugins.append(cls)
