# This file is part of sale_confirmed2quotation module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._transitions.add(
                ('processing', 'draft'),\
                )
        cls._buttons['draft']['invisible'] = ~Eval('state').in_(
                        ['cancelled', 'quotation', 'processing'])

    @classmethod
    def draft(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        Group = pool.get('res.group')
        ModelData = pool.get('ir.model.data')

        transaction = Transaction()

        # Check if production module is installed
        production_installed = False
        if hasattr(sales[0], 'productions'):
            production_installed = True
            Production = pool.get('production')
            SaleProduction = pool.get('sale.line-production')

        user_id = transaction.user
        if user_id != 0:
            group = Group(ModelData.get_id('sale_processing2confirmed',
                        'group_sale_process2draft')).id
            groups = transaction.context['groups']

        to_write = []
        to_delete_invoices = []
        to_delete_shipments = []
        to_delete_shipments_return = []
        to_delete_productions = []
        to_delete_prod_sale = []
        for sale in sales:
            if sale.state != 'processing':
                continue

            if user_id != 0:
                if group not in groups:
                    raise UserError(gettext(
                        'sale_processing2confirmed.user_group_process2draft'))

            if sale.invoices:
                to_delete_invoices += sale.invoices

            if sale.shipments or sale.shipment_returns:
                to_delete_shipments += sale.shipments
                to_delete_shipments_return += sale.shipment_returns

            if production_installed:
                to_delete_productions += sale.productions
                to_delete_prod_sale += SaleProduction.search([
                    ('sale_line', 'in', [s.id for s in sale.lines])])
            to_write.extend(([sale], {'state': 'draft'}))

        if to_write:
            cls.write(*to_write)

        with Transaction().set_user(0):
            if to_delete_invoices:
                Invoice.delete(to_delete_invoices)
            if to_delete_shipments:
                ShipmentOut.delete(to_delete_shipments)
            if to_delete_shipments_return:
                ShipmentOutReturn.delete(to_delete_shipments_return)
            if production_installed and to_delete_productions:
                SaleProduction.delete(to_delete_prod_sale)
                Production.delete(to_delete_productions)

        super(Sale, cls).draft(sales)
