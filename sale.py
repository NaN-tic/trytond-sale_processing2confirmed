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
    def process(cls, sales):
        if Transaction().context.get('_sale_processing2confirmed_draft'):
            return
        super().process(sales)

    @classmethod
    def draft(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        Group = pool.get('res.group')
        ModelData = pool.get('ir.model.data')

        transaction = Transaction()

        if not sales:
            return

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
        super().draft(sales)

        with Transaction().set_user(0), Transaction().set_context(
                _sale_processing2confirmed_draft=True):
            if to_delete_invoices:
                Invoice.delete(to_delete_invoices)
            if to_delete_shipments:
                ShipmentOut.draft(to_delete_shipments)
                ShipmentOut.delete(to_delete_shipments)
            if to_delete_shipments_return:
                ShipmentOutReturn.draft(to_delete_shipments_return)
                ShipmentOutReturn.delete(to_delete_shipments_return)
            if production_installed and to_delete_productions:
                SaleProduction.delete(to_delete_prod_sale)
                Production.delete(to_delete_productions)


class SaleDropShipment(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons['draft']['invisible'] = ~Eval('allow_draft', False)
        if 'allow_draft' not in cls._buttons['draft']['depends']:
            cls._buttons['draft']['depends'].append('allow_draft')

    def get_allow_draft(self, name):
        if not super().get_allow_draft(name):
            return False
        return all(shipment.state in {'draft', 'waiting', 'cancelled'}
            for shipment in self.drop_shipments)

    @classmethod
    def draft(cls, sales):
        pool = Pool()
        DropShipment = pool.get('stock.shipment.drop')
        PurchaseRequest = pool.get('purchase.request')
        SaleLine = pool.get('sale.line')

        drop_shipments = []
        requests = []
        lines = []
        for sale in sales:
            if any(shipment.state in {'shipped', 'done'}
                    for shipment in sale.drop_shipments):
                raise UserError(gettext(
                        'sale_processing2confirmed'
                        '.msg_sale_draft_drop_shipment',
                        sale=sale.rec_name))
            drop_shipments.extend(sale.drop_shipments)
            for line in sale.lines:
                request = line.purchase_request
                if not request:
                    continue
                if request.purchase_line:
                    if request.customer:
                        lines.append(line)
                else:
                    requests.append(request)

        if drop_shipments or requests or lines:
            with Transaction().set_user(0), Transaction().set_context(
                    _sale_processing2confirmed_draft=True):
                DropShipment.cancel([shipment for shipment in drop_shipments
                        if shipment.state != 'cancelled'])
                DropShipment.delete(drop_shipments)
                if requests:
                    PurchaseRequest.delete(requests)
                if lines:
                    SaleLine.write(lines, {'purchase_request': None})
        with Transaction().set_context(_sale_processing2confirmed_draft=True):
            super().draft(sales)
