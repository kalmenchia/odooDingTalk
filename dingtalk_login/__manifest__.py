# -*- coding: utf-8 -*-
{
    'name': "钉钉集成-扫码/免登",
    'summary': """用于支持钉钉扫码登录和钉钉应用内免登到odoo""",
    'description': """用于支持钉钉扫码登录和钉钉应用内免登到odoo""",
    'author': "E-GlobalSCM(Kalmen),XueFeng.Su",
    'website': "https://www.instant-erp.com",
    'category': 'dingtalk',
    'version': '14.1.1',
    'license': 'OPL-1',
    'depends': ['dingtalk_base', 'auth_oauth','mos_app_base'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'data': [
        'data/auth_oauth_data.xml',
        'views/web_templates.xml',

        'wizard/update_user_dingtalk_oauth_access.xml',
    ],

}
