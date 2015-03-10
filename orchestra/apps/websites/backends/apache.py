import textwrap
import os
import re

from django.template import Template, Context
from django.utils.translation import ugettext_lazy as _

from orchestra.apps.orchestration import ServiceController
from orchestra.apps.resources import ServiceMonitor

from .. import settings


class Apache2Backend(ServiceController):
    model = 'websites.Website'
    related_models = (
        ('websites.Content', 'website'),
    )
    verbose_name = _("Apache 2")
    
    def save(self, site):
        context = self.get_context(site)
        extra_conf = self.get_content_directives(site)
        if site.protocol is 'https':
            extra_conf += self.get_ssl(site)
        extra_conf += self.get_security(site)
        extra_conf += self.get_redirect(site)
        context['extra_conf'] = extra_conf
        
        apache_conf = Template(textwrap.dedent("""\
            # {{ banner }}
            <VirtualHost {{ ip }}:{{ site.port }}>
                ServerName {{ site.domains.all|first }}\
            {% if site.domains.all|slice:"1:" %}
                ServerAlias {{ site.domains.all|slice:"1:"|join:' ' }}{% endif %}\
            {% if access_log %}
                CustomLog {{ access_log }} common{% endif %}\
            {% if error_log %}
                ErrorLog {{ error_log }}{% endif %}
                SuexecUserGroup {{ user }} {{ group }}\
            {% for line in extra_conf.splitlines %}
                {{ line | safe }}{% endfor %}
                #IncludeOptional /etc/apache2/extra-vhos[t]/{{ site_unique_name }}.con[f]
            </VirtualHost>"""
        ))
        apache_conf = apache_conf.render(Context(context))
        apache_conf += self.get_protections(site)
        context['apache_conf'] = apache_conf
        
        self.append(textwrap.dedent("""\
            {
                echo -e '%(apache_conf)s' | diff -N -I'^\s*#' %(sites_available)s -
            } || {
                echo -e '%(apache_conf)s' > %(sites_available)s
                UPDATED=1
            }""") % context
        )
        self.enable_or_disable(site)
    
    def delete(self, site):
        context = self.get_context(site)
        self.append("a2dissite %(site_unique_name)s.conf && UPDATED=1" % context)
        self.append("rm -fr %(sites_available)s" % context)
    
    def commit(self):
        """ reload Apache2 if necessary """
        self.append('[[ $UPDATED == 1 ]] && service apache2 reload || true')
    
    def get_content_directives(self, site):
        directives = ''
        for content in site.contents.all().order_by('-path'):
            directive = content.webapp.get_directive()
            method, agrs = directive[0], directive[1:]
            method = getattr(self, 'get_%s_directives' % method)
            directives += method(content, *args)
        return directives
    
    def get_static_directives(self, content, app_path):
        context = self.get_content_context(content)
        context['app_path'] = app_path
        return "Alias %(location)s %(path)s\n" % context
    
    def get_fpm_directives(self, content, socket_type, socket, app_path):
        if socket_type == 'unix':
            target = 'unix:%(socket)s|fcgi://127.0.0.1%(app_path)s/'
            if content.path != '/':
                target = 'unix:%(socket)s|fcgi://127.0.0.1%(app_path)s/$1'
        elif socket_type == 'tcp':
            target = 'fcgi://%(socket)s%(app_path)s/$1'
        else:
            raise TypeError("%s socket not supported." % socket_type)
        context = self.get_content_context(content)
        context.update({
            'app_path': app_path,
            'socket': socket,
        })
        return textwrap.dedent("""\
            ProxyPassMatch ^%(location)s/(.*\.php(/.*)?)$ {target}
            Alias %(location)s/ %(app_path)s/
            """.format(target=target) % context
        )
    
    def get_fcgi_directives(self, content, app_path, wrapper_path):
        context = self.get_content_context(content)
        context.update({
            'app_path': app_path,
            'wrapper_path': wrapper_path,
        })
        fcgid = textwrap.dedent("""\
            Alias %(location)s %(app_path)s
            ProxyPass %(location)s !
            <Directory %(app_path)s>
                Options +ExecCGI
                AddHandler fcgid-script .php
                FcgidWrapper %(wrapper_path)s\
            """) % context
        for option in content.webapp.options.filter(name__startswith='Fcgid'):
            fcgid += "        %s %s\n" % (option.name, option.value)
        fcgid += "</Directory>\n"
        return fcgid
    
    def get_ssl(self, site):
        cert = settings.WEBSITES_DEFAULT_HTTPS_CERT
        custom_cert = site.options.filter(name='ssl')
        if custom_cert:
            cert = tuple(custom_cert[0].value.split())
        # TODO separate directtives?
        directives = textwrap.dedent("""\
            SSLEngine on
            SSLCertificateFile %s
            SSLCertificateKeyFile %s\
            """ % cert
        )
        return directives
    
    def get_security(self, site):
        directives = ''
        for rules in site.options.filter(name='sec_rule_remove'):
            for rule in rules.value.split():
                directives += "SecRuleRemoveById %i\n" % int(rule)
        for modsecurity in site.options.filter(name='sec_rule_off'):
            directives += textwrap.dedent("""\
                <LocationMatch %s>
                    SecRuleEngine Off
                </LocationMatch>\
                """ % modsecurity.value)
        if directives:
            directives = '<IfModule mod_security2.c>\n%s\n</IfModule>' % directives
        return directives
    
    def get_redirect(self, site):
        directives = ''
        for redirect in site.options.filter(name='redirect'):
            if re.match(r'^.*[\^\*\$\?\)]+.*$', redirect.value):
                directives += "RedirectMatch %s" % redirect.value
            else:
                directives += "Redirect %s" % redirect.value
        return directives
    
    def get_protections(self, site):
        protections = ''
        context = self.get_context(site)
        for protection in site.options.filter(name='directory_protection'):
            path, name, passwd = protection.value.split()
            path = os.path.join(context['root'], path)
            passwd = os.path.join(self.USER_HOME % context, passwd)
            protections += textwrap.dedent("""
                <Directory %s>
                    AllowOverride All
                    #AuthPAM_Enabled off
                    AuthType Basic
                    AuthName %s
                    AuthUserFile %s
                    <Limit GET POST>
                        require valid-user
                    </Limit>
                </Directory>""" % (path, name, passwd)
            )
        return protections
    
    def enable_or_disable(self, site):
        context = self.get_context(site)
        if site.is_active:
            self.append(textwrap.dedent("""\
                if [[ ! -f %(sites_enabled)s ]]; then
                    a2ensite %(site_unique_name)s.conf
                else
                    UPDATED=0
                fi""" % context
            ))
        else:
            self.append(textwrap.dedent("""\
                if [[ -f %(sites_enabled)s ]]; then
                    a2dissite %(site_unique_name)s.conf;
                else
                    UPDATED=0
                fi""" % context
            ))
    
    def get_username(self, site):
        option = site.options.filter(name='user_group').first()
        if option:
            return option.value.split()[0]
        return site.account.username
    
    def get_groupname(self, site):
        option = site.options.filter(name='user_group').first()
        if option and ' ' in option.value:
            user, group = option.value.split()
            return group
        return site.account.username
    
    def get_context(self, site):
        base_apache_conf = settings.WEBSITES_BASE_APACHE_CONF
        sites_available = os.path.join(base_apache_conf, 'sites-available')
        sites_enabled = os.path.join(base_apache_conf, 'sites-enabled')
        context = {
            'site': site,
            'site_name': site.name,
            'ip': settings.WEBSITES_DEFAULT_IP,
            'site_unique_name': site.unique_name,
            'user': self.get_username(site),
            'group': self.get_groupname(site),
            'sites_enabled': "%s.conf" % os.path.join(sites_enabled, site.unique_name),
            'sites_available': "%s.conf" % os.path.join(sites_available, site.unique_name),
            'access_log': site.get_www_access_log_path(),
            'error_log': site.get_www_error_log_path(),
            'banner': self.get_banner(),
        }
        return context
    
    def get_content_context(self, content):
        context = self.get_context(content.website)
        context.update({
            'type': content.webapp.type,
            'location': content.path,
            'app_name': content.webapp.name,
            'app_path': content.webapp.get_path(),
            'fpm_port': content.webapp.get_fpm_port(),
        })
        return context


class Apache2Traffic(ServiceMonitor):
    model = 'websites.Website'
    resource = ServiceMonitor.TRAFFIC
    verbose_name = _("Apache 2 Traffic")
    
    def prepare(self):
        super(Apache2Traffic, self).prepare()
        ignore_hosts = '\\|'.join(settings.WEBSITES_TRAFFIC_IGNORE_HOSTS)
        context = {
            'current_date': self.current_date.strftime("%Y-%m-%d %H:%M:%S %Z"),
            'ignore_hosts': '-v "%s"' % ignore_hosts if ignore_hosts else '',
        }
        self.append(textwrap.dedent("""\
            function monitor () {
                OBJECT_ID=$1
                INI_DATE=$(date "+%%Y%%m%%d%%H%%M%%S" -d "$2")
                END_DATE=$(date '+%%Y%%m%%d%%H%%M%%S' -d '%(current_date)s')
                LOG_FILE="$3"
                {
                    { grep %(ignore_hosts)s ${LOG_FILE} || echo -e '\\r'; } \\
                        | awk -v ini="${INI_DATE}" -v end="${END_DATE}" '
                            BEGIN {
                                sum = 0
                                months["Jan"] = "01"
                                months["Feb"] = "02"
                                months["Mar"] = "03"
                                months["Apr"] = "04"
                                months["May"] = "05"
                                months["Jun"] = "06"
                                months["Jul"] = "07"
                                months["Aug"] = "08"
                                months["Sep"] = "09"
                                months["Oct"] = "10"
                                months["Nov"] = "11"
                                months["Dec"] = "12"
                            } {
                                # date = [11/Jul/2014:13:50:41
                                date = substr($4, 2)
                                year = substr(date, 8, 4)
                                month = months[substr(date, 4, 3)];
                                day = substr(date, 1, 2)
                                hour = substr(date, 13, 2)
                                minute = substr(date, 16, 2)
                                second = substr(date, 19, 2)
                                line_date = year month day hour minute second
                                if ( line_date > ini && line_date < end)
                                    sum += $NF
                            } END {
                                print sum
                            }' || [[ $? == 1 ]] && true
                } | xargs echo ${OBJECT_ID}
            }""" % context))
    
    def monitor(self, site):
        context = self.get_context(site)
        self.append('monitor {object_id} "{last_date}" {log_file}'.format(**context))
    
    def get_context(self, site):
        return {
            'log_file': '%s{,.1}' % site.get_www_log_path(),
            'last_date': self.get_last_date(site.pk).strftime("%Y-%m-%d %H:%M:%S %Z"),
            'object_id': site.pk,
        }
