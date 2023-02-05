import logging
import time
from typing import List
from optibook import common_types as t
from optibook import ORDER_TYPE_IOC, ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
import random
import json
from math import floor

MARGIN = 0.01

logging.getLogger('client').setLevel('ERROR')
logger = logging.getLogger(__name__)

BASKET_INSTRUMENT_ID = 'C2_GREEN_ENERGY_ETF'
STOCK_INSTRUMENT_IDS = ['C2_SOLAR_CO', 'C2_WIND_LTD']

ALL_GREEN_IDS = ['C2_SOLAR_CO', 'C2_WIND_LTD', 'C2_GREEN_ENERGY_ETF']

BASKET_INSTRUMENT_ID1 = 'C1_FOSSIL_FUEL_ETF'
STOCK_INSTRUMENT_IDS1 = ['C1_GAS_INC', 'C1_OIL_CORP']

ALL_IDS = ['C2_SOLAR_CO', 'C2_WIND_LTD', 'C2_GREEN_ENERGY_ETF', 'C1_FOSSIL_FUEL_ETF', 'C1_GAS_INC', 'C1_OIL_CORP']


def print_report(e: Exchange):
    pnl = e.get_pnl()
    positions = e.get_positions()

    logger.info('BEGIN THIS CYCLE\'S TRADING TRANSACTION')
    logger.info(f'My current positions are: {json.dumps(positions, indent=3)}')
    logger.info(f'My PNL is: {pnl:.2f}')
    
    for s in ALL_IDS:
        my_trades = e.poll_new_trades(s)
        all_market_trades = e.poll_new_trade_ticks(s)
        logger.info(f'I have done {len(my_trades)} trade(s) in {s} since the last report. There have been {len(all_market_trades)} market trade(s) in total in {s} since the last report.')
    
    logger.info('END OF THIS CYCLE')


def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logger.info(f"Inserted order successfully, order_id='{order_response.order_id}'")
    else:
        logger.info(f"Unable to insert order with reason: '{order_response.success}'")


###################################################################################################


def trade_cycle(e: Exchange):
    basketProfiter(e, BASKET_INSTRUMENT_ID, STOCK_INSTRUMENT_IDS)
    
def trade_cycle_fossil(e: Exchange):
    basketProfiter(e, BASKET_INSTRUMENT_ID1, STOCK_INSTRUMENT_IDS1)

def basketProfiter(e: Exchange, basket_id, stocks):

    deleteOld(e, stocks + [basket_id])

    basket_book = e.get_last_price_book(basket_id)
    stock_a_book = e.get_last_price_book(stocks[0])
    stock_b_book = e.get_last_price_book(stocks[1])
    
    stock_a_asks = stock_a_book.asks
    stock_b_asks = stock_b_book.asks
    
    stock_a_bids = stock_a_book.bids
    stock_b_bids = stock_b_book.bids
    
    
    # Checks for indiscrepency of basket price and average individual instrument price
    if basket_book.bids and stock_a_asks and stock_b_asks:
        basket = basket_book.bids[0]
        stock_a_price = stock_a_asks[0].price
        stock_b_price = stock_b_asks[0].price
        
        if (stock_a_price + stock_b_price > 2 * basket.price):
            vol = find_vol(basket.price, min(stock_a_price, stock_b_price))
            
            for stock_id in stocks:
                vol = max_total_orders(stock_id, e, vol, -1)
                
            vol = floor(0.5 * max_total_orders(basket_id, e, 2 * vol, 1))
            
            if vol > 0:
                trade_with_market(basket_id,
                                  basket.price,
                                  SIDE_BID,
                                  SIDE_ASK,
                                  stock_a_book.instrument_id,
                                  stock_a_price,
                                  stock_b_book.instrument_id,
                                  stock_b_price,
                                  vol,
                                  e)
                print_report(e)
                time.sleep(sleep_duration_sec)
    
    if basket_book.asks and stock_a_bids and stock_b_bids:
        basket = basket_book.asks[0]
        stock_a_price = stock_a_bids[0].price
        stock_b_price = stock_b_bids[0].price
        
        # Checks for indiscrepency of basket price and average individual instrument price
        if (stock_a_price + stock_b_price < 2 * basket.price):
            vol = find_vol(basket.price, min(stock_a_price, stock_b_price))
            
            for stock_id in stocks:
                vol = max_total_orders(stock_id, e, vol, 1)
                
            vol = floor(0.5 * max_total_orders(basket_id, e, 2 * vol, -1))
            
            if vol > 0:
                trade_with_market(basket_id,
                                  basket.price,
                                  SIDE_ASK,
                                  SIDE_BID,
                                  stock_a_book.instrument_id,
                                  stock_a_price,
                                  stock_b_book.instrument_id,
                                  stock_b_price,
                                  vol,
                                  e)
                print_report(e)
                time.sleep(sleep_duration_sec)


    
def trade_with_market(basket_id, basket_price, side_type_basket, side_type_stock, stock_id, stock_price, stock_b_id, stock_b_price, vol, e: Exchange):
    
    r = e.insert_order(basket_id, 
                       price=basket_price, 
                       volume=2*vol, 
                       side=side_type_basket, 
                       order_type=ORDER_TYPE_IOC)
    if r.success:     
        s = e.insert_order(stock_id, 
                           price = stock_price,
                           volume=vol, 
                           side=side_type_stock,
                           order_type=ORDER_TYPE_IOC)
        
        if s.success:
            t = e.insert_order(stock_b_id, 
                               price = stock_b_price, 
                               volume=vol, 
                               side=side_type_stock,
                               order_type=ORDER_TYPE_IOC)
            
            if not t.success:
                e.delete_orders(stock_id)
                e.delete_orders(basket_id)
                e.delete_orders(stock_b_id)
            
        else:
            e.delete_orders(basket_id)
            e.delete_orders(stock_id)
            
    else:
        e.delete_orders(basket_id)
        
    print_order_response(r)
    print_order_response(s)
    print_order_response(t)
    

# Returns the correct buy number for the stock volumes(i.e half the basket volume), the first being the basket and the other two the individual stocks
def find_vol(etf: int, inst_a: int):
    if etf >= (inst_a * 2):
        return inst_a
    else:
        return floor(etf / 2)
        
def max_total_orders(stock_id, e: Exchange, volume, trade_int):
    positions = e.get_positions()
    pos_vol = positions[stock_id]
    if abs(trade_int * volume + pos_vol) > 500:
        return 500 - abs(pos_vol)
    else:
        return volume


def deleteOld(e: Exchange, ids):
    for o in ids:
        e.delete_orders(o)
        

###################################################################################################

query_time = 1/5000
sleep_duration_sec = 1

def main():
    exchange = Exchange()
    exchange.connect()

    while True:
        trade_cycle(exchange) # Runs the trade cycle for green energy solutions
        trade_cycle_fossil(exchange) # Runs the trade cycle for fossil fuel solutions
        logger.info(f'Iteration complete. Sleeping for {query_time} seconds')
        time.sleep(query_time)


if __name__ == '__main__':
    main()
