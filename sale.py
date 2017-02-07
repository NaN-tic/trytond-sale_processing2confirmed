# This file is part of sale_confirmed2quotation module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import Workflow, ModelView
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, If

__all__ = ['Sale']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._transitions.add(
                ('processing', 'draft'),
                )
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['quotation', 'processing']),
                    'icon': If(Eval('state') == 'quotation', 'tryton-go-next',
                        'tryton-go-previous'),
                    }
        })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        production_installed = False
        to_write = []
        # Check if production module is installed
        try:
            production_installed = sales[0].production is not None
        except AttributeError:
            pass

        if production_installed:
            Production = pool.get('production')

        to_delete_invoices = []
        to_delete_shipments = []
        to_delete_shipments_return = []
        to_delete_productions = []
        for sale in sales:
            if sale.state != 'processing':
                continue
            if sale.invoices:
                to_delete_invoices += sale.invoices

            if sale.shipments or sale.shipments_returns:
                to_delete_shipments += sale.shipments
                to_delete_shipments_return += sale.shipment_returns

            if production_installed:
                to_delete_productions += sale.productions
            to_write.extend(([sale], {'state': 'draft'}))

        if to_write:
            cls.write(*to_write)
            Invoice.delete(to_delete_invoices)
            ShipmentOut.delete(to_delete_shipments)
            ShipmentOutReturn.delete(to_delete_shipments_return)
            if production_installed:
                Production.delete(to_delete_productions)

        super(Sale, cls).draft(sales)
