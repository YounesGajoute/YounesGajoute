# utils/pid_controller.py

from simple_pid import PID
import logging
import time

class PIDControllerWrapper:
    """
    Extended wrapper around simple_pid's PID for pressure regulation
    in multi-chamber testing systems. Supports adaptive timing logic
    similar to custom regulation phases (fast/medium/fine).
    """

    def __init__(
        self,
        kp=0.3,
        ki=0.05,
        kd=0.02,
        setpoint=150.0,
        output_limits=(0.0, 1.0),
        sample_time=0.1
    ):
        self.logger = logging.getLogger("PIDControllerWrapper")
        self._setup_logger()

        self.setpoint = setpoint
        self.sample_time = sample_time
        self.last_pressure = None
        self.pressure_history = []

        self.pid = PID(kp, ki, kd, setpoint=self.setpoint)
        self.pid.sample_time = sample_time
        self.pid.output_limits = output_limits

        # Mode thresholds and timing (in seconds)
        self.modes = {
            "fast": {"threshold": 40, "pulse_on": 0.3, "pulse_off": 0.1},
            "medium": {"threshold": 15, "pulse_on": 0.2, "pulse_off": 0.2},
            "fine": {"threshold": 5, "pulse_on": 0.1, "pulse_off": 0.3},
        }

    def _setup_logger(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def update_setpoint(self, new_setpoint: float):
        self.logger.info(f"Updating setpoint: {new_setpoint}")
        self.setpoint = new_setpoint
        self.pid.setpoint = new_setpoint

    def compute(self, current_value: float) -> float:
        """Standard PID output computation."""
        output = self.pid(current_value)
        self.logger.debug(f"PID compute: input={current_value:.2f}, output={output:.3f}")
        return output

    def compute_adaptive_pulse(self, current_pressure: float) -> dict:
        """
        Computes adaptive pulse_on and pulse_off durations based on pressure error
        and rate of change, emulating manual control tuning logic.

        Returns:
            dict: {'pulse_on': float, 'pulse_off': float, 'mode': str}
        """
        error = self.setpoint - current_pressure
        abs_error = abs(error)

        # Determine control mode
        if abs_error > self.modes["fast"]["threshold"]:
            mode = "fast"
        elif abs_error > self.modes["medium"]["threshold"]:
            mode = "medium"
        else:
            mode = "fine"

        mode_config = self.modes[mode]

        # Compute pressure rate of change
        if self.last_pressure is not None:
            rate = (current_pressure - self.last_pressure) / self.sample_time
        else:
            rate = 0.0

        self.last_pressure = current_pressure
        self.pressure_history.append(current_pressure)
        if len(self.pressure_history) > 10:
            self.pressure_history.pop(0)

        avg_rate = sum(
            self.pressure_history[i] - self.pressure_history[i - 1]
            for i in range(1, len(self.pressure_history))
        ) / max(1, len(self.pressure_history) - 1)

        # Adjust pulse durations
        rate_factor = min(1.0, abs(avg_rate) / 10.0)
        adjusted_on = mode_config["pulse_on"] * (1 - rate_factor)
        adjusted_off = mode_config["pulse_off"] * (1 + rate_factor)

        self.logger.debug(
            f"[{mode.upper()}] error={error:.2f}, rate={rate:.2f}, "
            f"pulse_on={adjusted_on:.2f}, pulse_off={adjusted_off:.2f}"
        )

        return {
            "pulse_on": max(0.05, adjusted_on),
            "pulse_off": max(0.05, adjusted_off),
            "mode": mode,
        }

    def reset(self):
        """Reset internal state and PID controller."""
        self.pid.auto_mode = False
        self.pid.auto_mode = True
        self.pressure_history.clear()
        self.last_pressure = None
        self.logger.info("PID controller reset")

    def set_output_limits(self, min_val: float, max_val: float):
        self.pid.output_limits = (min_val, max_val)

    def get_output_limits(self):
        return self.pid.output_limits

    def get_parameters(self):
        return {
            "kp": self.pid.Kp,
            "ki": self.pid.Ki,
            "kd": self.pid.Kd,
            "setpoint": self.pid.setpoint,
            "limits": self.pid.output_limits
        }
