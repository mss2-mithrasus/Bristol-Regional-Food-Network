from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta


def checkout_view(request):
    """
    Display checkout page - TC-007, TC-008
    MINIMAL VERSION FOR TESTING
    """
    # Calculate minimum delivery date (48 hours from now)
    min_delivery_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    
    # Dummy data for testing
    context = {
        'cart_grouped_by_producer': {
            '1': {
                'producer_name': 'Bristol Valley Farm',
                'items': [
                    {
                        'product_name': 'Organic Carrots',
                        'quantity': 2,
                        'subtotal': 7.00
                    },
                    {
                        'product_name': 'Fresh Eggs',
                        'quantity': 1,
                        'subtotal': 3.50
                    }
                ],
                'subtotal': 10.50
            },
            '2': {
                'producer_name': 'Hillside Dairy',
                'items': [
                    {
                        'product_name': 'Fresh Milk',
                        'quantity': 2,
                        'subtotal': 8.00
                    }
                ],
                'subtotal': 8.00
            }
        },
        'is_multi_vendor': True,
        'min_delivery_date': min_delivery_date,
        'cart_subtotal': 18.50,
        'commission': 0.93,  # 5% of 18.50
        'total': 19.43,
        'customer': {
            'delivery_address': '45 Park Street, Bristol',
            'postcode': 'BS1 5JG',
            'email': 'customer@test.com'
        },
        'stripe_public_key': 'pk_test_DUMMY_KEY_FOR_TESTING'
    }
    
    return render(request, 'checkout.html', context)


def order_history_view(request):
    """
    Display customer order history - TC-021
    MINIMAL VERSION FOR TESTING
    """
    # Dummy orders for testing
    context = {
        'orders': [
            {
                'order_id': 1,
                'order_number': 'ORD-ABC12345',
                'created_at': date.today(),
                'total_amount': 25.50,
                'payment_status': 'completed',
                'is_multi_vendor': True,
                'producer_orders': {
                    'all': [
                        {
                            'producer': {
                                'business_name': 'Bristol Valley Farm'
                            },
                            'delivery_date': date.today() + timedelta(days=3)
                        },
                        {
                            'producer': {
                                'business_name': 'Hillside Dairy'
                            },
                            'delivery_date': date.today() + timedelta(days=4)
                        }
                    ]
                }
            }
        ]
    }
    
    return render(request, 'order_history.html', context)


def order_confirmation_view(request, order_number):
    """
    Display order confirmation page
    MINIMAL VERSION FOR TESTING
    """
    context = {
        'order': {
            'order_number': order_number,
            'total_amount': 19.43,
            'producer_orders': {
                'all': [
                    {
                        'producer': {'business_name': 'Bristol Valley Farm'},
                        'delivery_date': date.today() + timedelta(days=3),
                        'items': {
                            'all': [
                                {'quantity': 2, 'product_name': 'Organic Carrots'},
                                {'quantity': 1, 'product_name': 'Fresh Eggs'}
                            ]
                        }
                    }
                ]
            }
        },
        'customer': {
            'email': 'customer@test.com'
        }
    }
    
    return render(request, 'order_confirmation.html', context)