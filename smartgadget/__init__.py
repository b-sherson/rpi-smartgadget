"""
Communicate with a Sensirion SHTxx Smart Gadget.
"""
import logging
from math import exp, log10
from datetime import datetime

from msl.network import manager, ssh

__author__ = 'Joseph Borbely'
__copyright__ = '\xa9 2019 - 2020, ' + __author__
__version__ = '0.1.0.dev0'

# if you change this value then you must also update the name of the
# virtual environment that is created in rpi-setup.sh
RPI_EXE_PATH = 'shtenv/bin/smartgadget'

logger = logging.getLogger(__package__)


def connect(*, host='raspberrypi', rpi_username='pi', rpi_password=None, timeout=10, **kwargs):
    """Connect to the :class:`~smartgadget.sht3x.SHT3XService` on the Raspberry Pi.

    Parameters
    ----------
    host : :class:`str`, optional
        The hostname or IP address of the Raspberry Pi.
    rpi_username : :class:`str`, optional
        The username for the Raspberry Pi.
    rpi_password : :class:`str`, optional
        The password for `rpi_username`.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait for the connection.
    kwargs
        Keyword arguments that are passed to :func:`~msl.network.manager.run_services`.

    Returns
    -------
    :class:`~smartgadget.client.SmartGadgetClient`
        A connection to the :class:`~smartgadget.sht3x.SHT3XService` on the Raspberry Pi.
    """
    console_script_path = '/home/{}/{}'.format(rpi_username, RPI_EXE_PATH)
    ssh.start_manager(host, console_script_path, ssh_username=rpi_username,
                      ssh_password=rpi_password, timeout=timeout, as_sudo=True, **kwargs)

    kwargs['host'] = host
    return SmartGadgetClient('Smart Humigadget', **kwargs)


def start_service_on_rpi():
    """Starts the Network :class:`~msl.network.manager.Manager` and the :class:`~smartgadget.sht3x.SHT3XService`.

    This function should only be called from the ``smartgadget`` console script (see setup.py).
    """
    kwargs = ssh.parse_console_script_kwargs()
    if kwargs.get('auth_login', False) and ('username' not in kwargs or 'password' not in kwargs):
        raise ValueError(
            'The Manager is using a login for authentication but the SmartGadgetService '
            'does not know the username and password to use to connect to the Manager'
        )
    interface = kwargs.pop('interface', None)
    manager.run_services(SHT3XService(interface=interface), **kwargs)


def kill_manager(*, host='raspberrypi', rpi_username='pi', rpi_password=None, timeout=10, **kwargs):
    """Kill the Network :class:`~msl.network.manager.Manager` on the Raspberry Pi.

    Parameters
    ----------
    host : :class:`str`, optional
        The hostname or IP address of the Raspberry Pi.
    rpi_username : :class:`str`, optional
        The username for the Raspberry Pi.
    rpi_password : :class:`str`, optional
        The password for `rpi_username`.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait for the connection.
    kwargs
        Keyword arguments that are passed to :meth:`~paramiko.client.SSHClient.connect`.
    """
    ssh_client = ssh.connect(host, username=rpi_username, password=rpi_password, timeout=timeout, **kwargs)
    lines = ssh.exec_command(ssh_client, 'ps aux | grep smartgadget')
    pids = [line.split()[1] for line in lines if RPI_EXE_PATH in line]
    for pid in pids:
        try:
            ssh.exec_command(ssh_client, 'sudo kill -9 ' + pid)
        except:
            pass
    ssh_client.close()


def invwexeq(vp, c, d):
    """The Wexler equation, used for calculating vapor pressure

    Parameters
    ----------
    vp : :class:`float`
        The vapor pressure [hPa].
    c, d : :class:'list(float), list(float)'
        Various derived constants

    Returns
    -------
    :class:`float`
        The vapor pressure
    """

    # Calculate dew point
    sumt = 0
    sumb = 0
    for i in range(0, 3):
        sumt = sumt + (c[i] * (log10(vp) / (log10(exp(1))) ** i))
        sumb = sumb + (d[i] * (log10(vp) / (log10(exp(1))) ** i))
    dp = sumt / sumb - 273.15

def dewpoint(temperature, humidity, model='hardy', isdew=True):
        """Calculate the dew point.

        Parameters
        ----------
        temperature : :class:`float`
            The temperature [degree C].
        humidity : :class:`float`
            The humidity [%RH].
        model : :class:'string'
            The dew point model
        isdew : :class:'string'
            True is dew point, False is frost point

        Returns
        -------
        :class:`float`
            The dew point [degree C].
        """

        if model == 'hardy':
            # Hardy is a robust model, and is the one currently used in MSL humidity calibrations
            # RANGE Undefined
            if isdew == True:
                a = [-2.8365744 * 10 ** 3, -6.028076559 * 10 ** 3, 1.954263612 * 10, -2.737830188 * 10 ** -2,
                     1.6261698 * 10 ** -5, 7.0229056 * 10 ** -10, -1.8680009 * 10 ** -13, 2.7150305]
                c = [2.0798233 * 10 ** 2, -2.0156028 * 10, 4.6778925 * 10 ** -1, -9.2288067 * 10 ** -6]
                d = [1, -1.3319669 * 10 ** -1, 5.6577518 * 10 ** -3, -7.5172865 * 10 ** -5]
            else:
                a = [0, -5.8666426 * 10 ** 3, 2.232870244 * 10, 1.39387003 * 10 ** -2, -3.4262402 * 10 ** -5,
                     2.7040955 * 10 ** -8, 0, 6.7063522]
                c = [2.1257969 * 10 ** 2, -1.0264612 * 10, 1.4354796 * 10 ** -1, 0]
                d = [1, -8.2871619 * 10 ** -2, 2.3540411 * 10 ** -3, -2.4363951 * 10 ** -5]
            vp = wexeq(temperature, humidity, a)
            dp = invwexeq(vp, c, d)
        # Missing appropriate range

        elif model == 'wexler':
            #
            if isdew == True:
                if temperature < 0 or temperature > 100:
                    # The Wexler dew model is only valid between 0 and +100 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-0 to +100)')
                a = [-2.9912729 * 10 ** 3, -6.0170128 * 10 ** 3, 1.887643854 * 10, -2.8354721 * 10 ** -2,
                     1.7838301 * 10 ** -5, -8.4150417 * 10 ** -10, 4.4412543 * 10 ** -13, 2.858487]
                c = [2.0798233 * 10 ** 2, -2.0156028 * 10, 4.6778925 * 10 ** -1, -9.2288067 * 10 ** -6]
                d = [1, -1.3319669 * 10 ** -1, 5.6577518 * 10 ** -3, -7.5172865 * 10 ** -5]
            else:
                if temperature < -100 or temperature > 0.01:
                    # The Wexler frost model is only valid between -100 and +0.01 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-100 to +0.01)')
                a = [0, -5.6745359 * 10 ** 3, 6.3925247, -9.677843 * 10 ** -3, 6.22157 * 10 ** -7,
                     2.0747825 * 10 ** -9, -9.484024 * 10 ** -13, 4.163509]
                c = [2.1257969 * 10 ** 2, -1.0264612 * 10, 1.4354796 * 10 ** -1, 0]
                d = [1, -8.2871619 * 10 ** -2, 2.3540411 * 10 ** -3, -2.4363951 * 10 ** -5]
            vp = wexeq(temperature, humidity, a)
            dp = invwexeq(vp, c, d)
        # Missing description
        # Missing appropriate range
        # Check c and d values

        elif model == 'sonntag':
            #
            if isdew == True:
                if temperature < 0 or temperature > 100:
                    # The Sonntag dew model is only valid between 0 and +100 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-0 to +100)')
                a = [0, -6.0969385 * 10 ** 3, 2.12409642 * 10, -2.711193 * 10 ** -2,
                     1.673952 * 10 ** -5, 0, 0, 2.433502]
                c = [2.0798233 * 10 ** 2, -2.0156028 * 10 ** 1, 4.6778925 * 10 ** -1, -9.2288067 * 10 ** -6]
                d = [1, -1.3319669 * 10 ** -1, 5.6577518 * 10 ** -3, -7.5172865 * 10 ** -5]
            else:
                if temperature < -100 or temperature > 0.01:
                    # The Sonntag frost model is only valid between -100 and +0.01 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-100 to +0.01)')
                a = [0, -6.0245282 * 10 ** 3, 2.932707 * 10, 1.0613868 * 10 ** -2, -3.4262402 * 10 ** -5,
                     2.7040955 * 10 ** -8, 0, 6.7063522 * 10 ** -1]
                c = [2.1257969 * 10 ** 2, -1.0264612 * 10 ** 1, 1.4354796 * 10 ** -1, 0]
                d = [1, -8.2871619 * 10 ** -2, 2.3540411 * 10 ** -3, -2.4363951 * 10 ** -5]
            vp = wexeq(temperature, humidity, a)
            dp = invwexeq(vp, c, d)
        # Missing description
        # Missing appropriate range
        # Check c and d values

        elif model == 'clausiusclapeyron':
            #
            # RANGE?
            # DEW VS FROST?
            tk = temperature + 273.15
            e0 = 611
            lrv = 5423
            t0 = 273.15
            vp = e0 * exp(lrv * (1 / t0 - 1 / tk)) * humidity / 100

            dp = 1 / (1 / t0 - (log10(vp / e0) / lrv)/log10(exp(1))) - 273.15
        # Missing description
        # Missing appropriate range
        # Missing dew/frost distinction

        elif model == 'ardenbuck':
            #
            # Calculate vapor pressure
            a = 611.2
            d = 234.5
            if isdew == True:
                if temperature < -0 or temperature > 50:
                    # The Arden Buck dew model is only valid between 0 and +50 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-0 to +50)')
                b = 17.368
                c = 238.88

            else:
                if temperature < -40 or temperature > 0:
                    # The Arden Buck frost model is only valid between -40 and +0 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-40 to +0)')
                b = 17.966
                c = 247.15

            vp = a * exp(b - (temperature / d) / (temperature / (c + temperature))) * humidity / 100

            # Calculate dew point
            dp = c * (log10(vp / a) / log10(exp(1)) / (b - (log10(vp / a) / log10(exp(1)))))
        # Missing description

        elif model == 'magnus':
            # Magnus is a less accurate but commonly used model
            # Calculate vapor pressure
            a = 611.2
            if isdew == True:
                if temperature < -45 or temperature > 60:
                    # The Magnus dew model is only valid between -45 and +60 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-45 to +60)')
                b = 17.62
                c = 243.12
            else:
                if temperature < -65 or temperature > 0.01:
                    # The Magnus frost model is only valid between -65 and +0.01 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-65 to +0.01)')
                b = 22.46
                c = 272.62

            vp = a * exp(b * temperature / (c + temperature)) * humidity / 100

            # Calculate dew point
            dp = c * (log10(vp / a) / log10(exp(1)) / (b - (log10(vp / a) / log10(exp(1)))))

        elif model == 'wagnerpruss':
            #
            if isdew == True:
                if temperature < -20 or temperature > 350:
                    # The Wagner & Pruss dew model is only valid between -20 and +350 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-20 to +350)')

                # Calculate vapor pressure
                c = [-7.85951783, 1.84408259, -11.7866497, 22.6807411, -15.9618719, 1.80122502]
                pc = 220640
                tc = 647.096
                tk = temperature + 273.15
                x = 1.0 - tk / tc
                y = (tc / tk) * (c[1] * x + c[2] * x**1.5 + c[3] * x**3 + c[4] * x**3.5 + c[5] * x**4 + c[6] * x**7.5)
                pws = pc * exp(y)
                vp = pws * humidity / 100

                # Calculate dew point
                if -20 <= temperature <= 50:
                    a, m, tn = 6.116441, 7.591386, 240.7263
                elif 50 < temperature < 100:
                    a, m, tn = 6.004918, 7.337936, 229.3975
                elif 100 <= temperature <= 150:
                    a, m, tn = 5.856548, 7.277310, 225.1033
                elif 150 < temperature <= 200:
                    a, m, tn = 6.002859, 7.290361, 227.1704
                elif 200 < temperature <= 350:
                    a, m, tn = 9.980622, 7.388931, 263.1239
                else:
                    assert False, 'should never get here'

            else:
                if temperature < -70 or temperature > 0:
                    # The Wagner & Pruss frost model is only valid between -70 and +0 degree C
                    raise ValueError('Temperature', temperature, 'is out of range (-70 to 0)')

                # Calculate vapor pressure
                c = [-13.928169, 34.707823]
                pn = 6.11657
                tn = 273.16
                tk = temperature + 273.15
                x = tk / tn
                y = (c[1] * (1 - x ** -1.5) + c[2] * (1 - x ** -1.25))
                pws = pn * exp(y)
                vp = pws * humidity / 100

                # Calculate dew point
                if -70 <= temperature <= 0:
                   a, m, tn = 6.114742, 9.778707, 273.1466
                else:
                    assert False, 'should never get here'

            dp = tn / (m / log10(vp / a) - 1.0)
        # Missing description

        elif model == 'simple':
            # This is an overly simple approximation, here purely for completeness
            if humidity < 50:
                # The simple model is only valid above 50%RH
                raise ValueError('Humidity', humidity, 'is out of range (>50%)')
            dp = temperature - (100-humidity)/5

        else:
            # The desired model doesn't exist
            raise ValueError(model, 'is not a valid model')

        return dp


def timestamp_to_milliseconds(obj):
    """Convert an object into a timestamp in milliseconds.

    Parameters
    ----------
    obj
        A :class:`~datetime.datetime` object, an ISO-8601 formatted :class:`str`,
        a :class:`float` in seconds, or an :class:`int` in milliseconds.

    Returns
    -------
    :class:`int`
        The timestamp in milliseconds.
    """
    if isinstance(obj, int):  # in milliseconds
        return obj

    if isinstance(obj, float):  # in seconds
        return round(obj * 1e3)

    if isinstance(obj, str):  # an ISO-8601 string
        string = obj.replace('T', ' ')
        fmt = '%Y-%m-%d %H:%M:%S'
        if '.' in string:
            fmt += '.%f'
        obj = datetime.strptime(string, fmt)

    return round(obj.timestamp() * 1e3)


def milliseconds_to_datetime(milliseconds):
    """Convert a timestamp in milliseconds to a :class:`~datetime.datetime`.

    Parameters
    ----------
    milliseconds : :class:`int`
        A timestamp in milliseconds.

    Returns
    -------
    :class:`~datetime.datetime`
        The `milliseconds` converted to a :class:`~datetime.datetime` object.
    """
    return datetime.fromtimestamp(milliseconds * 1e-3)


from .client import SmartGadgetClient
from .sht3x import SHT3XService
from .shtc1 import SHTC1Service
