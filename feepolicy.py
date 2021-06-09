import math


class FeePolicy:
    def __init__(self, base_fee, fee_rate, fee_spread, time_lock_delta):
        self.base_fee = base_fee
        self.fee_rate = fee_rate
        self.fee_spread = fee_spread
        self.time_lock_delta = time_lock_delta

    def calculate(self, channel):
        ratio = channel.local_balance / (channel.capacity - channel.commit_fee)
        # -1.0 = all funds local
        # +1.0 = all funds remote
        ratio = 1.0 - 2.0 * ratio
        coef = math.exp(self.fee_spread * ratio)
        fee_rate = 0.000001 * coef * self.fee_rate
        if fee_rate < 0.000001:
            fee_rate = 0.000001
        base_fee = self.base_fee
        time_lock_delta = self.time_lock_delta
        return base_fee, fee_rate, time_lock_delta
