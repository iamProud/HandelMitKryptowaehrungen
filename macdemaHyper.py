# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
from email.policy import default
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from functools import reduce

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# This class is a sample. Feel free to customize it.
class MACDEMAHYPER(IStrategy):
    #buy    
    buy_ema= IntParameter(150, 250, default=245, space="buy")

    buy_macd_fast = IntParameter(7, 20, default=18, space="buy")
    buy_macd_slow = IntParameter(20, 30, default=27, space="buy")
    buy_signal_smothing = IntParameter(5, 15, default=15, space="buy")
    
    buy_cross_below_enabled = BooleanParameter(default=False, space="buy")

    #sell
    sell_macd_fast = IntParameter(7, 20, default=19, space="sell")
    sell_macd_slow = IntParameter(20, 30, default=20, space="sell")
    sell_signal_smothing = IntParameter(5, 15, default=8, space="sell")

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 2

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 100
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.218

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    
    # Optimal timeframe for the strategy.
    timeframe = '1h'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the "ask_strategy" section in the config.
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        'buy': 'limit',
        'sell': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Optional order time in force.
    order_time_in_force = {
        'buy': 'gtc',
        'sell': 'gtc'
    }

    plot_config = {
        'main_plot': {
            'tema': {},
            'sar': {'color': 'white'},
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
            },
            "RSI": {
                'rsi': {'color': 'red'},
            }
        }
    }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        # Momentum Indicators
        # ------------------------------------
        # MACD
        frames = [dataframe]

        for val1 in self.buy_macd_fast.range:
            for val2 in self.buy_macd_slow.range:
                newMacd = True

                for val3 in self.buy_signal_smothing.range:
                    frame = DataFrame()

                    macd = ta.MACD(dataframe, fastperiod=val1, slowperiod=val2, signalperiod=val3)
                    if newMacd:
                        frame[f'macd_{val1}_{val2}'] = macd['macd']
                        newMacd = False

                    frame[f'macdsignal_{val1}_{val2}_{val3}'] = macd['macdsignal']
                    frames.append(frame)
        

        # # EMA - Exponential Moving Average
        for emaLength in self.buy_ema.range:
            frame = DataFrame()
            frame[f'ema{emaLength}'] = ta.EMA(dataframe, timeperiod=emaLength)
            frames.append(frame)
            
        merged_frame = pd.concat(frames, axis=1)

        # Retrieve best bid and best ask from the orderbook
        # ------------------------------------
        """
        # first check if dataprovider is available
        if self.dp:
            if self.dp.runmode.value in ('live', 'dry_run'):
                ob = self.dp.orderbook(metadata['pair'], 1)
                dataframe['best_bid'] = ob['bids'][0][0]
                dataframe['best_ask'] = ob['asks'][0][0]
        """

        return merged_frame

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        conditions = []

        # EMA Condition
        conditions.append(dataframe['close'] > dataframe[f'ema{self.buy_ema.value}'])

        # MACD Condition
        val1 = dataframe[f'macd_{self.buy_macd_fast.value}_{self.buy_macd_slow.value}']
        val2 = dataframe[f'macdsignal_{self.buy_macd_fast.value}_{self.buy_macd_slow.value}_{self.buy_signal_smothing.value}']
        print(val1)
        print(type(val1))

        conditions.append(qtpylib.crossed_above(val1, val2))

        if self.buy_cross_below_enabled.value:
            conditions.append(dataframe[f'macdsignal_{self.buy_macd_fast.value}_{self.buy_macd_slow.value}_{self.buy_signal_smothing.value}'] < 0)
        
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with sell column
        """
        conditions = []
        conditions.append(qtpylib.crossed_above(dataframe[f'macdsignal_{self.sell_macd_fast.value}_{self.sell_macd_slow.value}_{self.sell_signal_smothing.value}'], dataframe[f'macd_{self.sell_macd_fast.value}_{self.sell_macd_slow.value}']))

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'sell'] = 1

        return dataframe
