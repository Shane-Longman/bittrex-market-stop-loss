#!/usr/bin/python3
# -*- coding: utf-8 -*-

import plac
import requests
import time
import json
import sys
import hashlib
import hmac
import decimal as D
from typing import Tuple


def check_number(n: str):
    try:
        n = float(n)
    except:
        return -1
    if n <= 0:
        return -2
    return 0


def bittrex_request(method: str, uri: str, body: str='', auth: Tuple=None):
    headers = dict()
    if auth:
        key, secret = auth
        key = str(key)
        secret = str(secret)
        body_hash = hashlib.sha512(json.dumps(body).encode("latin-1")).hexdigest()
        timestamp = str(int(time.time() * 1000))
        to_sign = ''.join([str(timestamp), uri, method, body_hash, ""])
        signature = hmac.new(str(secret).encode('latin-1'), to_sign.encode('latin-1'), hashlib.sha512).hexdigest()
        headers = {
            'Api-Key': key,
            'Api-Timestamp': timestamp,
            'Api-Content-Hash': body_hash,
            'Api-Signature': signature,
        }

    rv = requests.request(method, url=uri, headers=headers, json=body)

    return rv


def build_request_body(market_symbol: str, price: D.Decimal, quantity: D.Decimal):
    return {
        "operand": "LTE",
        "marketSymbol": market_symbol,
        "triggerPrice": f"{price}",
        "orderToCreate": {
            "direction": "sell",
            "marketSymbol": market_symbol,
            "type": "MARKET",
            "timeInForce": "IMMEDIATE_OR_CANCEL",
            "quantity": f"{quantity}"
        }
    }


def main(
    dry_run : ("Do not place the order, just print order details.", 'flag', 'd'),
    no_verify : ("Do not verify order price and quantity values. Verification requires pulling additional data from the exchange, that will be used to assert proper number of decimal places and minimum order size.", 'flag', 'n'),
    verbose : ("Enable verbose output.", 'flag', 'v'),
    market_symbol : ("Symbol of the market where the SL order shall be placed, e.g. BTC-USD.", 'positional', None, str),
    size : ("Quantity of base currency (e.g. BTC on the BTC/USD market) to place the SELL order for.", 'positional', None, str),
    price : ("Price level that shall trigger execution of Stop Loss Market order.", 'positional', None, str),
    api_key : ("API Key with 'Trade' privileges", 'positional', None, str),
    api_secret : ("API Secret with 'Trade' privileges", 'positional', None, str),
    ):

    if check_number(size) < 0:
        print(f"[!] Specified order size {size} is not a positive number")
        return 1

    if check_number(price) < 0:
        print(f"[!] Specified trigger price {price} is not a positive number")
        return 1

    size = D.Decimal(size)
    price = D.Decimal(price)

    if not no_verify:
        res = bittrex_request("GET", f"https://api.bittrex.com/v3/markets/{market_symbol}")
        if not res.ok:
            print(f"[!] Market Info request failed: [{res.status_code}] {res.json()}")
            return 1
        market_info = res.json()
        min_size = D.Decimal(market_info['minTradeSize'])
        precision = int(market_info['precision'])

        if verbose:
            print(f"[i] Minimum trade size for {market_symbol} is {min_size}")
            print(f"[i] Precision for {market_symbol} is {precision}")

        if size < min_size:
            print(f"[!] Order size {size} is below required minimum order size value of {min_size} for market {market_symbol}")
            return 1
        _, _, exponent = D.Decimal(price).normalize().as_tuple()
        decimal_digits = -exponent

        if verbose:
            print(f"[i] Precision of requested price is {decimal_digits}")

        if precision < decimal_digits:
            print(f"[!] Price {price} has precision which exceeds {precision} decimal places.")
            return 1
        price = price.quantize(D.Decimal('0.1') ** precision)

    request_body = build_request_body(market_symbol, price=price, quantity=size)

    if verbose or dry_run:
        print(f"[i] Order request: {request_body}")

    if not dry_run:
        res = bittrex_request("POST", "https://api.bittrex.com/v3/conditional-orders", request_body, auth=(api_key, api_secret))

        if not res.ok:
            print(f"[!] Order request failed: [{res.status_code}] {res.json()}")
            return 1
        else:
            print(f"[i] Stop Loss Market order created successfully: {res.json()}")

    return 0


if __name__ == "__main__":
    rv = plac.call(main)
    sys.exit(rv)
