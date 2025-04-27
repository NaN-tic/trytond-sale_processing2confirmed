import unittest
from decimal import Decimal

from proteus import Model
from trytond.model.exceptions import AccessError
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Activate sale_confirmed2processing
        config = activate_modules('sale_processing2confirmed')

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        Group = Model.get('res.group')
        config._context = User.get_preferences(True, config.context)

        # Create sale user
        sale_user = User()
        sale_user.name = 'Sale'
        sale_user.login = 'sale'
        sale_group, = Group.find([('name', '=', 'Sales')])
        sale_user.groups.append(sale_group)
        sale_user.save()

        # Create stock user
        stock_user = User()
        stock_user.name = 'Stock'
        stock_user.login = 'stock'
        stock_group, = Group.find([('name', '=', 'Stock')])
        stock_user.groups.append(stock_group)
        stock_user.save()

        # Create account user
        account_user = User()
        account_user.name = 'Account'
        account_user.login = 'account'
        account_group, = Group.find([('name', '=', 'Accounting')])
        account_user.groups.append(account_group)
        account_user.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create parties
        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()
        customer = Party(name='Customer')
        customer.customer_tax_rule = None
        customer.save()

        # Create category account
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory()
        account_category.name = 'Taxable'
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.accounting = True
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        gram, = ProductUom.find([('name', '=', 'Gram')])
        kilo, = ProductUom.find([('name', '=', 'Kilogram')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'PROD1'
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('10.0')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.salable = True
        template.save()
        product1, = template.products
        product1.code = 'PROD1'
        product1.cost_price = Decimal('5.0')
        product1.save()
        template = ProductTemplate()
        template.name = 'PROD2'
        template.default_uom = gram
        template.type = 'goods'
        template.list_price = Decimal('10.0')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.salable = True
        template.save()
        product2, = template.products
        product2.code = 'PROD2'
        product2.cost_price = Decimal('5.0')
        product2.save()
        template = ProductTemplate()
        template.name = 'PROD3'
        template.default_uom = kilo
        template.type = 'goods'
        template.list_price = Decimal('10.0')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.salable = True
        template.save()
        product3, = template.products
        product3.code = 'PROD3'
        product3.cost_price = Decimal('5.0')
        product3.save()
        template = ProductTemplate()
        template.name = 'service'
        template.default_uom = unit
        template.type = 'service'
        template.salable = True
        template.list_price = Decimal('30')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.salable = True
        template.save()
        service, = template.products
        service.cost_price = Decimal('10')
        service.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create an Inventory
        config.user = stock_user.id
        Inventory = Model.get('stock.inventory')
        Location = Model.get('stock.location')
        storage, = Location.find([
            ('code', '=', 'STO'),
        ])
        inventory = Inventory()
        inventory.location = storage
        inventory_line = inventory.lines.new(product=product1)
        inventory_line.quantity = 100.0
        inventory_line.expected_quantity = 0.0
        inventory_line = inventory.lines.new(product=product2)
        inventory_line.quantity = 50.0
        inventory_line.expected_quantity = 0.0
        inventory_line = inventory.lines.new(product=product3)
        inventory_line.quantity = 20.0
        inventory_line.expected_quantity = 0.0
        inventory.click('confirm')
        self.assertEqual(inventory.state, 'done')

        # Create a sale
        config.user = sale_user.id
        Sale = Model.get('sale.sale')
        SaleLine = Model.get('sale.line')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product1
        sale_line.quantity = 2.0
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product2
        sale_line.quantity = 20.0
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product3
        sale_line.quantity = 10.0
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = service
        sale_line.quantity = 1
        sale.save()
        sale.click('quote')
        sale.click('confirm')

        # Duplicate Sale
        posted_invoice_sale, = Sale.duplicate(
            [sale], {'description': 'Posted invoice sale'})
        posted_shipment_sale, = Sale.duplicate(
            [sale], {'description': 'Posted shipment sale'})

        # Process sale
        self.assertEqual(sale.state, 'processing')
        self.assertEqual(len(sale.shipments), 1)
        self.assertEqual(len(sale.shipment_returns), 0)
        self.assertEqual(len(sale.invoices), 1)

        # Go back to confirmed on original sale
        self.assertEqual(sale.state, 'processing')

        sale.click('draft')
        self.assertEqual(sale.state, 'draft')
        self.assertEqual(len(sale.shipments), 0)
        self.assertEqual(len(sale.shipment_returns), 0)
        self.assertEqual(len(sale.invoices), 0)

        # Process posted invoice sales
        posted_invoice_sale.click('quote')
        posted_invoice_sale.click('confirm')
        invoices = [invoice for invoice in posted_invoice_sale.invoices]

        # Post invoice
        config.user = account_user.id

        for invoice in invoices:
            invoice.click('post')

        # Draft invoice sale
        config.user = sale_user.id

        with self.assertRaises(AccessError):
            posted_invoice_sale.click('draft')

        self.assertEqual(posted_invoice_sale.state, 'processing')

        # Validate Shipments
        posted_shipment_sale.click('quote')
        posted_shipment_sale.click('confirm')
        shipment, = posted_shipment_sale.shipments
        config.user = stock_user.id
        shipment.click('assign_try')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('do')
        self.assertEqual(shipment.state, 'done')

        # Draft shipment sale
        config.user = sale_user.id

        with self.assertRaises(AccessError):
            posted_invoice_sale.click('draft')

        self.assertEqual(posted_shipment_sale.state, 'processing')
