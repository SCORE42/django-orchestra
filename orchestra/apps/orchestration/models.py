import copy
import socket

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.module_loading import autodiscover_modules
from django.utils.translation import ugettext_lazy as _

from orchestra.core.validators import validate_ip_address, ValidationError
from orchestra.models.fields import NullableCharField
#from orchestra.utils.apps import autodiscover

from . import settings
from .backends import ServiceBackend


class Server(models.Model):
    """ Machine runing daemons (services) """
    name = models.CharField(_("name"), max_length=256, unique=True)
    address = NullableCharField(_("address"), max_length=256, blank=True,
            null=True, unique=True, help_text=_("IP address or domain name"))
    description = models.TextField(_("description"), blank=True)
    os = models.CharField(_("operative system"), max_length=32,
            choices=settings.ORCHESTRATION_OS_CHOICES,
            default=settings.ORCHESTRATION_DEFAULT_OS)
    
    def __unicode__(self):
        return self.name
    
    def get_address(self):
        if self.address:
            return self.address
        return self.name
    
    def get_ip(self):
        if self.address:
            return self.address
        try:
            validate_ip_address(self.name)
        except ValidationError:
            return socket.gethostbyname(self.name)
        else:
            return self.name


class BackendLog(models.Model):
    RECEIVED = 'RECEIVED'
    TIMEOUT = 'TIMEOUT'
    STARTED = 'STARTED'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    ERROR = 'ERROR'
    REVOKED = 'REVOKED'
    # Special state for mocked backendlogs
    EXCEPTION = 'EXCEPTION'
    
    STATES = (
        (RECEIVED, RECEIVED),
        (TIMEOUT, TIMEOUT),
        (STARTED, STARTED),
        (SUCCESS, SUCCESS),
        (FAILURE, FAILURE),
        (ERROR, ERROR),
        (REVOKED, REVOKED),
    )
    
    backend = models.CharField(_("backend"), max_length=256)
    state = models.CharField(_("state"), max_length=16, choices=STATES,
            default=RECEIVED)
    server = models.ForeignKey(Server, verbose_name=_("server"),
            related_name='execution_logs')
    script = models.TextField(_("script"))
    stdout = models.TextField(_("stdout"))
    stderr = models.TextField(_("stdin"))
    traceback = models.TextField(_("traceback"))
    exit_code = models.IntegerField(_("exit code"), null=True)
    task_id = models.CharField(_("task ID"), max_length=36, unique=True, null=True,
            help_text="Celery task ID when used as execution backend")
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)
    
    class Meta:
        get_latest_by = 'id'
    
    def __unicode__(self):
        return "%s@%s" % (self.backend, self.server)
    
    @property
    def execution_time(self):
        return (self.updated_at-self.created_at).total_seconds()
    
    def backend_class(self):
        return ServiceBackend.get_backend(self.backend)


class BackendOperation(models.Model):
    """
    Encapsulates an operation, storing its related object, the action and the backend.
    """
    DELETE = 'delete'
    SAVE = 'save'
    MONITOR = 'monitor'
    EXCEEDED = 'exceeded'
    RECOVERY = 'recovery'
    
    log = models.ForeignKey('orchestration.BackendLog', related_name='operations')
    backend = models.CharField(_("backend"), max_length=256)
    action = models.CharField(_("action"), max_length=64)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    
    instance = generic.GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        verbose_name = _("Operation")
        verbose_name_plural = _("Operations")
    
    def __unicode__(self):
        return '%s.%s(%s)' % (self.backend, self.action, self.instance)
    
    def __hash__(self):
        """ set() """
        backend = getattr(self, 'backend', self.backend)
        return hash(backend) + hash(self.instance) + hash(self.action)
    
    def __eq__(self, operation):
        """ set() """
        return hash(self) == hash(operation)
    
    @classmethod
    def create(cls, backend, instance, action, servers=None):
        op = cls(backend=backend.get_name(), instance=instance, action=action)
        op.backend = backend
        # instance should maintain any dynamic attribute until backend execution
        # deep copy is prefered over copy otherwise objects will share same atributes (queryset cache)
        op.instance = copy.deepcopy(instance)
        op.servers = servers
        return op
    
    @classmethod
    def execute(cls, operations, async=False):
        from . import manager
        return manager.execute(operations, async=async)
    
    @classmethod
    def execute_action(cls, instance, action):
        backends = ServiceBackend.get_backends(instance=instance, action=action)
        operations = [cls.create(backend_cls, instance, action) for backend_cls in backends]
        return cls.execute(operations)
    
    def preload_context(self):
        """
        Heuristic
        Running get_context will prevent most of related objects do not exist errors
        """
        if self.action == self.DELETE:
            if hasattr(self.backend, 'get_context'):
                self.backend().get_context(self.instance)
    
    def backend_class(self):
        return ServiceBackend.get_backend(self.backend)


autodiscover_modules('backends')


class Route(models.Model):
    """
    Defines the routing that determine in which server a backend is executed
    """
    backend = models.CharField(_("backend"), max_length=256,
            choices=ServiceBackend.get_choices())
    host = models.ForeignKey(Server, verbose_name=_("host"))
    match = models.CharField(_("match"), max_length=256, blank=True, default='True',
            help_text=_("Python expression used for selecting the targe host, "
                        "<em>instance</em> referes to the current object."))
#    async = models.BooleanField(default=False)
#    method = models.CharField(_("method"), max_lenght=32, choices=method_choices,
#            default=MethodBackend.get_default())
    is_active = models.BooleanField(_("active"), default=True)
    
    class Meta:
        unique_together = ('backend', 'host')
    
    def __unicode__(self):
        return "%s@%s" % (self.backend, self.host)
    
    @property
    def backend_class(self):
        return ServiceBackend.get_backend(self.backend)
    
    @classmethod
    def get_servers(cls, operation, **kwargs):
        cache = kwargs.get('cache', {})
        servers = []
        backend_cls = operation.backend
        key = (backend_cls.get_name(), operation.action)
        try:
            routes = cache[key]
        except KeyError:
            cache[key] = []
            for route in cls.objects.filter(is_active=True, backend=backend_cls.get_name()):
                for action in backend_cls.get_actions():
                    _key = (route.backend, action)
                    try:
                        cache[_key].append(route)
                    except KeyError:
                        cache[_key] = [route]
            routes = cache[key]
        for route in routes:
            if route.matches(operation.instance):
                servers.append(route.host)
        return servers
    
    def clean(self):
        if not self.match:
            self.match = 'True'
        if self.backend:
            backend_model = self.backend_class.model
            try:
                obj = backend_model.objects.all()[0]
            except IndexError:
                return
            try:
                bool(self.matches(obj))
            except Exception, exception:
                name = type(exception).__name__
                message = exception.message
                raise ValidationError(': '.join((name, message)))
    
    def matches(self, instance):
        safe_locals = {
            'instance': instance,
            'obj': instance,
            instance._meta.model_name: instance,
        }
        return eval(self.match, safe_locals)
    
    def enable(self):
        self.is_active = True
        self.save()
    
    def disable(self):
        self.is_active = False
        self.save()
