# -*- coding: utf-8 -*-
import json
import logging
import werkzeug
import requests
from werkzeug.exceptions import BadRequest
from odoo import SUPERUSER_ID, api, http, _, exceptions
from odoo import registry as registry_get
from odoo.addons.auth_oauth.controllers.main import OAuthLogin
from odoo.addons.web.controllers.main import (login_and_redirect, ensure_db, set_cookie_and_redirect)
from odoo.http import request
from odoo.addons.dingtalk_base.tools import dingtalk_tool as dt
#todo: kalmen@temp disable from odoo.addons.mos_app_base.controllers.main import WhatsappController
_logger = logging.getLogger(__name__)


class DingTalkLogin(OAuthLogin):

    @http.route('/web/dingtalk/login', type='http', auth='none', website=True, sitemap=False)
    def web_dingtalk_login(self, *args, **kw):
        """
        构造扫码登录页面
        :param args:
        :param kw:
        :return:
        """
        ensure_db()
        if not request.session.uid:
            return request.render('dingtalk_login.dingtalk_login_signup')
        if request.session.uid:
            return http.redirect_with_hash('/web')
        request.uid = request.session.uid
        try:
            context = request.env['ir.http'].webclient_rendering_context()
            response = request.render('web.webclient_bootstrap', qcontext=context)
            response.headers['X-Frame-Options'] = 'DENY'
            return response
        except exceptions.AccessError:
            if request.session.uid:
                request.session.uid = False
            if request.session.login:
                request.session.login = False
            return request.render('dingtalk_login.dingtalk_login_signup')

    @http.route('/web/dingtalk/get/companys', type='http', auth='public', website=True, sitemap=False)
    def dingtalk_get_companys(self):
        result = {
            "company_list": request.env['res.company'].sudo().search_read([], ['name', 'id'])
        }
        return json.dumps(result)

    @http.route('/web/dingtalk/get_login_url', type='http', auth="none")
    def dingtalk_get_login_url(self, **kw):
        """
        拼接访问钉钉的验证用户的url
        :param kw:
        :return:
        """
        params_data = request.params.copy()
        local_url = params_data.get('local_url')
        company_id = int(params_data.get('company_id'))
        config = request.env['dingtalk.config'].sudo().search([('company_id', '=', company_id)], limit=1)
        if not config:
            return json.dumps({'state': False, 'error': '该公司未设置扫码登录'})
        redirect_url = "{}/web/dingtalk/login/redirect".format(local_url)
        url = "https://oapi.dingtalk.com/connect/oauth2/sns_authorize?appid={}&response_type=code&scope=" \
              "snsapi_login&redirect_uri={}&state={}".format(config.login_id, redirect_url, company_id)
        data = json.dumps({'state': True, "encode_url": url, 'callback_url': redirect_url})
        return data

    @http.route('/web/dingtalk/login/redirect', type='http', auth="none", website=True, sitemap=False)
    def web_dingtalk_login_redirect(self, **kw):
        """
        接受钉钉返回的扫码登录结果
        :param kw:
        :return:
        """
        params_data = request.params.copy()
        params_data['providers'] = self.list_providers()
        _logger.info(">>>钉钉扫码登录返回code参数为：{}".format(params_data.get('code')))
        _logger.info(params_data)
        company_id = params_data.get('state')
        if not company_id:
            params_data['error'] = _("钉钉扫码返回的数据格式不正确，请重试！")
            return request.render('web.login', params_data)
        try:
            company_id = int(company_id)
            user_info = dt.get_userinfo_by_code(request, params_data.get('code'), company_id)
            msg = ">>>用户身份信息:{}".format(user_info)
            _logger.info(msg)
            #domain = [('din_unionid', '=', user_info.get('unionid')), ('company_id', '=', company_id)]
            domain = [('din_unionid', '=', user_info.get('unionid'))]
            employee = request.env['hr.employee'].sudo().search(domain, limit=1)
            if not employee.user_id:
                params_data['error'] = _("员工[{}]未关联系统登录用户，请联系管理员处理！".format(employee.name))
                #try to email for all employee which din_isAdmin and din_isBoss
                #pdf = self.env.ref('account.account_invoices').sudo().render_qweb_pdf(self.sale_order_id.mapped('invoice_ids').ids)[0]
                #attachment_ids.append(self.env['ir.attachment'].create({
                #    'name': 'Invoice.pdf',
                #    'type': 'binary',
                #    'datas': base64.encodestring(pdf),
                #    'datas_fname': 'Invoice.pdf',
                #    'res_model': 'bot.temp.order',
                #    'res_id': self.id,
                #    'mimetype': 'application/pdf'
                #}).id)                
                #template = self.env.ref('mos_app_base.temp_order_summary')
                #if template:
                #    template.write({
                #        'attachment_ids': [(6, 0, attachment_ids)],
                #    })	
                #    template.send_mail(self.id, force_send=True)                
                    #try to whatsapp if module is available
                
                #todo: kalmen@temp disable
                #wc = WhatsappController()
                #dbname = request.session.db
                #msg = "Hi {name} of {company}, new user not found in users/employees/partners trying to login, please check and add him/her to #system.\n".format(
                #            name="Super admin", company=dbname) + msg
                #phone = request.env['ir.config_parameter'].sudo().get_param('mos_app_base.company_main_whatsapp_no')
                #if not phone:
                #    print('No whatsapp number found for company')
                #    params_data['error'] = params_data['error'] + _("\nNo whatsapp number found for company")
                #else:
                #    wc.send_message( False, _(msg), phone=phone ,api_type="apichat_io")
                    
                return request.render('web.login', params_data)
            else:
                return self.dingtalk_employee_login(employee, params_data)
        except Exception as e:
            params_data['error'] = str(e)
            return request.render('web.login', params_data)

    def dingtalk_employee_login(self, employee, params_data):
        """
        利用员工进行系统登录
        :param employee:
        :param params_data:
        :return:
        """
        ensure_db()
        dbname = request.session.db
        if not http.db_filter([dbname]):
            return BadRequest()
        registry = registry_get(dbname)
        with registry.cursor() as cr:
            try:
                #env = api.Environment(cr, SUPERUSER_ID, {})
                if not employee:
                    params_data['error'] = "登录时发生错误：{}".format('员工不存在')
                    return request.render('web.login', params_data)                    
                else:
                    if not employee.ding_id:
                        params_data['error'] = "登录时发生错误：{}".format('员工ding_id不存在')
                        return request.render('web.login', params_data)
                                                
                    _logger.info(employee.ding_id)
                    credentials = request.env['res.users'].sudo().auth_oauth('dingtalk_login', employee.ding_id)
                    cr.commit()
                    url = '/web'
                    _logger.info(credentials)
                    resp = login_and_redirect(*credentials, redirect_url=url)
                    if werkzeug.urls.url_parse(resp.location).path == '/web':
                        resp.location = '/'
                    return resp
            except Exception as e:
                params_data['error'] = "登录时发生错误：{}".format(str(e))
                return request.render('web.login', params_data)


class OAuthController(OAuthLogin):

    @http.route('/web/dingtalk/auto/login', type='http', auth='public', website=True)
    def web_dingtalk_auto_login(self, **kw):
        """
        免登入口
        :param kw:
        :return:
        """
        ensure_db()
        logging.info(">>>用户正在使用免登...")
        if request.session.uid:
            return http.redirect_with_hash('/web')
        # 获取用于免登的公司corp_id
        config = request.env['dingtalk.config'].sudo().search([('m_login', '=', True)], limit=1)
        if not config:
            params_data = request.params.copy()
            params_data['providers'] = self.list_providers()
            params_data['error'] = "系统没有配置可用于免登的公司！"
            return request.render('web.login', params_data)
        return request.render('dingtalk_login.dingtalk_auto_login_signup', {'corp_id': config.corp_id})

    @http.route('/web/dingtalk/auto/login/action', type='http', auth='none', website=True, sitemap=False)
    def web_dingtalk_auto_signin_action(self, **kw):
        """
        通过获得的【免登授权码或者临时授权码】获取用户信息
        :param kw:
        :return:
        """
        params_data = request.params.copy()
        params_data['providers'] = self.list_providers()
        logging.info(">>>免登授权码: %s", params_data.get('authCode'))
        config = request.env['dingtalk.config'].sudo().search([('m_login', '=', True)], limit=1)
        client = dt.get_client(request, dt.get_dingtalk_config(request, config.company_id))
        try:
            result = client.user.getuserinfo(params_data.get('authCode'))
        except Exception as e:
            params_data['error'] = str(e)
            return request.render('web.login', params_data)
        #kalmen:-->ding_id ==> din_jobnumber
        #domain = [('ding_id', '=', result.userid), ('company_id', '=', config.company_id.id)]
        domain = [('din_jobnumber', '=', result.userid), ('company_id', '=', config.company_id.id)]
        employee = request.env['hr.employee'].sudo().search(domain, limit=1)
        if not employee:
            params_data['error'] = _("员工[{}]未关联系统登录用户，请联系管理员处理！".format(employee.name))
            return request.render('web.login', params_data)
        _logger.info(">>>员工：{}正在尝试登录系统".format(employee.name))
        if not employee.ding_id:
            params_data['error'] = _("员工[{}]不存在钉钉ID，请维护后再试!".format(employee.name))
            return request.render('web.login', params_data)
        if not employee.user_id:
            params_data['error'] = _("你还没有关联系统用户，请联系管理员处理！")
            return request.render('web.login', params_data)
        ensure_db()
        dbname = request.session.db
        if not http.db_filter([dbname]):
            return BadRequest()
        registry = registry_get(dbname)
        with registry.cursor() as cr:
            try:
                #env = api.Environment(cr, SUPERUSER_ID, {})
                credentials = request.env['res.users'].sudo().auth_oauth('dingtalk_login', employee.ding_id)
                cr.commit()
                url = '/web'
                resp = login_and_redirect(*credentials, redirect_url=url)
                if werkzeug.urls.url_parse(resp.location).path == '/web':
                    resp.location = '/'
                return resp
            except Exception as e:
                params_data['error'] = "登录时发生错误：{}".format(str(e))
                return request.render('web.login', params_data)
