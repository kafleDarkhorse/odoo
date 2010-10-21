##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
from tools.translate import _

class sale_advance_payment_inv(osv.osv_memory):
    _name = "sale.advance.payment.inv"
    _description = "Sale Advance Payment Invoice"
    _columns = {
        'product_id': fields.many2one('product.product', 'Advance Product', required=True,
            help="Select a product of type service which is called 'Advance Product'. You may have to create it and set it as a default value on this field."),
        'amount': fields.float('Advance Amount', size=(16, 2), required=True, help="The amount to be invoiced in advance."),
        'qtty': fields.float('Quantity', size=(16, 2), required=True),
    }
    _defaults = {
        'qtty': 1.0
    }

    def create_invoices(self, cr, uid, ids, context={}):
        """
             To create invoices.

             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs if we want more than one
             @param context: A standard dictionary

             @return:

        """
        list_inv = []
        obj_sale = self.pool.get('sale.order')
        obj_lines = self.pool.get('account.invoice.line')
        inv_obj = self.pool.get('account.invoice')

        for sale_adv_obj in self.browse(cr, uid, ids):
            for sale in obj_sale.browse(cr, uid, context['active_ids']):
                create_ids = []
                ids_inv = []
                if sale.order_policy == 'postpaid':
                    raise osv.except_osv(
                        _('Error'),
                        _("You cannot make an advance on a sale order \
                             that is defined as 'Automatic Invoice after delivery'."))
                val = obj_lines.product_id_change(cr, uid, [], sale_adv_obj.product_id.id,
                        uom = False, partner_id = sale.partner_id.id, fposition_id = sale.fiscal_position.id)
                line_id = obj_lines.create(cr, uid, {
                    'name': val['value']['name'],
                    'account_id': val['value']['account_id'],
                    'price_unit': sale_adv_obj.amount,
                    'quantity': sale_adv_obj.qtty,
                    'discount': False,
                    'uos_id': val['value']['uos_id'],
                    'product_id': sale_adv_obj.product_id.id,
                    'invoice_line_tax_id': [(6, 0, val['value']['invoice_line_tax_id'])],
                    'account_analytic_id': sale.project_id.id or False,
                    #'note':'',
                })
                create_ids.append(line_id)
                inv = {
                    'name': sale.client_order_ref or sale.name,
                    'origin': sale.name,
                    'type': 'out_invoice',
                    'reference': False,
                    'account_id': sale.partner_id.property_account_receivable.id,
                    'partner_id': sale.partner_id.id,
                    'address_invoice_id': sale.partner_invoice_id.id,
                    'address_contact_id': sale.partner_order_id.id,
                    'invoice_line': [(6, 0, create_ids)],
                    'currency_id': sale.pricelist_id.currency_id.id,
                    'comment': '',
                    'payment_term': sale.payment_term.id,
                    'fiscal_position': sale.fiscal_position.id or sale.partner_id.property_account_position.id
                }

                inv_id = inv_obj.create(cr, uid, inv)
                inv_obj.button_reset_taxes(cr, uid, [inv_id], context=context)

                for inv in sale.invoice_ids:
                    ids_inv.append(inv.id)
                ids_inv.append(inv_id)
                obj_sale.write(cr, uid, sale.id, {'invoice_ids': [(6, 0, ids_inv)]})
                list_inv.append(inv_id)
        #
        # If invoice on picking: add the cost on the SO
        # If not, the advance will be deduced when generating the final invoice
        #
                if sale.order_policy == 'picking':
                    self.pool.get('sale.order.line').create(cr, uid, {
                        'order_id': sale.id,
                        'name': val['value']['name'],
                        'price_unit': -sale_adv_obj.amount,
                        'product_uom_qty': sale_adv_obj.qtty,
                        'product_uos_qty': sale_adv_obj.qtty,
                        'product_uos': val['value']['uos_id'],
                        'product_uom': val['value']['uos_id'],
                        'product_id': sale_adv_obj.product_id.id,
                        'discount': False,
                        'tax_id': [(6, 0, val['value']['invoice_line_tax_id'])],
                    }, context)

        context.update({'invoice_id':list_inv})

        return {
            'name': 'Open Invoice',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.open.invoice',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

sale_advance_payment_inv()

class sale_open_invoice(osv.osv_memory):
    _name = "sale.open.invoice"
    _description = "Sale Open Invoice"
    def open_invoice(self, cr, uid, ids, context):

        """
             To open invoice.
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs if we want more than one
             @param context: A standard dictionary
             @return:

        """

        mod_obj = self.pool.get('ir.model.data')
        for advance_pay in self.browse(cr, uid, ids):
            result = mod_obj._get_id(cr, uid, 'account', 'view_account_invoice_filter')
            id = mod_obj.read(cr, uid, result, ['res_id'])
            form_id = mod_obj._get_id(cr, uid, 'account', 'invoice_form')
            form_res = mod_obj.browse(cr, uid, form_id, context=context).res_id
            tree_id = mod_obj._get_id(cr, uid, 'account', 'invoice_tree')
            tree_res = mod_obj.browse(cr, uid, tree_id, context=context).res_id
        return {
            'name': _('Advance Invoice'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'account.invoice',
            'res_id': int(context['invoice_id'][0]),
            'view_id': False,
            'views': [(form_res, 'form'), (tree_res, 'tree')],
            'context': "{'type': 'out_invoice'}",
            'type': 'ir.actions.act_window',
         }

sale_open_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
