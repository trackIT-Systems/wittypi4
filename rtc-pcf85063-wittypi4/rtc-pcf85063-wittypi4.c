// SPDX-License-Identifier: GPL-2.0
/*
 * I2C register-window proxy for the PCF85063 RTC on Witty Pi 4.
 *
 * The MCU at 0x08 exposes the RTC at register base 0x36 and does not
 * support bulk I2C transfers. This driver presents a nested adapter
 * the in-tree rtc-pcf85063 driver can bind to.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <linux/version.h>

#define WITTYPI_RTC_REG_BASE	0x36
#define WITTYPI_RTC_VIRT_ADDR	0x51
#define WITTYPI_XFER_RETRIES	3
#define WITTYPI_XFER_RETRY_MS	100

struct wittypi_rtc_proxy {
	struct i2c_client *client;
	struct i2c_adapter adap;
	struct i2c_client *rtc;
};

static int wittypi_parent_xfer(struct i2c_client *client,
			       struct i2c_msg *msgs, int num)
{
	int try, ret;

	for (try = 0; try < WITTYPI_XFER_RETRIES; try++) {
		ret = i2c_transfer(client->adapter, msgs, num);
		if (ret == num)
			return 0;

		if (try == WITTYPI_XFER_RETRIES - 1) {
			dev_err(&client->dev,
				"I2C transfer failed after %d retries (ret %d)\n",
				WITTYPI_XFER_RETRIES, ret);
			return ret < 0 ? ret : -EIO;
		}

		dev_warn(&client->dev, "I2C error %d, retrying %d of %d\n",
			 ret, try + 1, WITTYPI_XFER_RETRIES);
		msleep(WITTYPI_XFER_RETRY_MS);
	}

	return -EIO;
}

static int wittypi_parent_write_byte(struct i2c_client *client, u8 reg, u8 val)
{
	u8 buf[2] = { reg, val };
	struct i2c_msg msg = {
		.addr = client->addr,
		.flags = 0,
		.len = 2,
		.buf = buf,
	};

	return wittypi_parent_xfer(client, &msg, 1);
}

static int wittypi_parent_write_reg(struct i2c_client *client, u8 reg)
{
	struct i2c_msg msg = {
		.addr = client->addr,
		.flags = 0,
		.len = 1,
		.buf = &reg,
	};

	return wittypi_parent_xfer(client, &msg, 1);
}

static int wittypi_parent_read_byte(struct i2c_client *client, u8 reg, u8 *val)
{
	u8 r = reg;
	struct i2c_msg msgs[2] = {
		{
			.addr = client->addr,
			.flags = 0,
			.len = 1,
			.buf = &r,
		},
		{
			.addr = client->addr,
			.flags = I2C_M_RD,
			.len = 1,
			.buf = val,
		},
	};

	return wittypi_parent_xfer(client, msgs, 2);
}

static int wittypi_xfer_write(struct i2c_client *client, struct i2c_msg *msg)
{
	u8 reg;
	int i, err;

	if (msg->len < 1)
		return -EINVAL;

	reg = msg->buf[0] + WITTYPI_RTC_REG_BASE;

	if (msg->len == 1)
		return wittypi_parent_write_reg(client, reg);

	for (i = 1; i < msg->len; i++) {
		err = wittypi_parent_write_byte(client, reg + (i - 1),
						msg->buf[i]);
		if (err)
			return err;
	}

	return 0;
}

static int wittypi_xfer_read(struct i2c_client *client, u8 virt_reg,
			     struct i2c_msg *msg)
{
	u8 reg = virt_reg + WITTYPI_RTC_REG_BASE;
	int i, err;

	for (i = 0; i < msg->len; i++) {
		err = wittypi_parent_read_byte(client, reg + i, &msg->buf[i]);
		if (err)
			return err;
	}

	return 0;
}

static int wittypi_master_xfer(struct i2c_adapter *adap, struct i2c_msg *msgs,
			       int num)
{
	struct wittypi_rtc_proxy *priv = adap->algo_data;
	struct i2c_client *client = priv->client;
	int n, err;

	if (num < 1)
		return -EINVAL;

	for (n = 0; n < num; n++) {
		if (msgs[n].addr != WITTYPI_RTC_VIRT_ADDR)
			return -ENXIO;
		if (msgs[n].flags & I2C_M_NOSTART)
			return -EOPNOTSUPP;
	}

	for (n = 0; n < num;) {
		if (n + 1 < num && !(msgs[n].flags & I2C_M_RD) &&
		    (msgs[n + 1].flags & I2C_M_RD)) {
			if (msgs[n].len < 1)
				return -EINVAL;

			err = wittypi_xfer_read(client, msgs[n].buf[0],
						&msgs[n + 1]);
			if (err)
				return err;
			n += 2;
			continue;
		}

		if (msgs[n].flags & I2C_M_RD)
			return -EOPNOTSUPP;

		err = wittypi_xfer_write(client, &msgs[n]);
		if (err)
			return err;
		n++;
	}

	return num;
}

static u32 wittypi_functionality(struct i2c_adapter *adap)
{
	return I2C_FUNC_I2C | I2C_FUNC_SMBUS_EMUL;
}

static const struct i2c_algorithm wittypi_algo = {
	.master_xfer = wittypi_master_xfer,
	.functionality = wittypi_functionality,
};

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 3, 0)
static int wittypi_rtc_proxy_probe(struct i2c_client *client,
				   const struct i2c_device_id *id)
#else
static int wittypi_rtc_proxy_probe(struct i2c_client *client)
#endif
{
	struct wittypi_rtc_proxy *priv;
	struct i2c_board_info info = {
		.type = "pcf85063a",
		.addr = WITTYPI_RTC_VIRT_ADDR,
	};
	int err;

	priv = devm_kzalloc(&client->dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	priv->client = client;
	i2c_set_clientdata(client, priv);

	snprintf(priv->adap.name, sizeof(priv->adap.name),
		 "wittypi4-rtc-proxy");
	priv->adap.owner = THIS_MODULE;
	priv->adap.class = 0;
	priv->adap.algo = &wittypi_algo;
	priv->adap.algo_data = priv;
	priv->adap.dev.parent = &client->dev;

	err = i2c_add_adapter(&priv->adap);
	if (err)
		return err;

	request_module("rtc-pcf85063");

	priv->rtc = i2c_new_client_device(&priv->adap, &info);
	if (IS_ERR(priv->rtc)) {
		err = PTR_ERR(priv->rtc);
		dev_err(&client->dev, "failed to create pcf85063a client: %d\n",
			err);
		goto err_del_adapter;
	}

	if (!priv->rtc->dev.driver) {
		dev_err(&client->dev,
			"in-tree rtc-pcf85063 did not bind; enable CONFIG_RTC_DRV_PCF85063\n");
		err = -ENODEV;
		goto err_unregister_rtc;
	}

	return 0;

err_unregister_rtc:
	i2c_unregister_device(priv->rtc);
	priv->rtc = NULL;
err_del_adapter:
	i2c_del_adapter(&priv->adap);
	return err;
}

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 11, 0)
static int wittypi_rtc_proxy_remove(struct i2c_client *client)
{
	struct wittypi_rtc_proxy *priv = i2c_get_clientdata(client);

	if (priv->rtc)
		i2c_unregister_device(priv->rtc);
	i2c_del_adapter(&priv->adap);

	return 0;
}
#else
static void wittypi_rtc_proxy_remove(struct i2c_client *client)
{
	struct wittypi_rtc_proxy *priv = i2c_get_clientdata(client);

	if (priv->rtc)
		i2c_unregister_device(priv->rtc);
	i2c_del_adapter(&priv->adap);
}
#endif

static const struct i2c_device_id wittypi_rtc_proxy_ids[] = {
	{ "wittypi4-rtc-proxy" },
	{ "pcf85063wp" },
	{}
};
MODULE_DEVICE_TABLE(i2c, wittypi_rtc_proxy_ids);

#ifdef CONFIG_OF
static const struct of_device_id wittypi_rtc_proxy_of_match[] = {
	{ .compatible = "uugear,wittypi4-rtc-proxy" },
	{ .compatible = "nxp,pcf85063wp" },
	{}
};
MODULE_DEVICE_TABLE(of, wittypi_rtc_proxy_of_match);
#endif

static struct i2c_driver wittypi_rtc_proxy_driver = {
	.driver = {
		.name = "rtc-pcf85063-wittypi4",
		.of_match_table = of_match_ptr(wittypi_rtc_proxy_of_match),
	},
	.probe = wittypi_rtc_proxy_probe,
	.remove = wittypi_rtc_proxy_remove,
	.id_table = wittypi_rtc_proxy_ids,
};

module_i2c_driver(wittypi_rtc_proxy_driver);

MODULE_AUTHOR("Søren Andersen <san@rosetechnology.dk>");
MODULE_DESCRIPTION("Witty Pi 4 PCF85063 I2C register-window proxy");
MODULE_LICENSE("GPL");
MODULE_SOFTDEP("pre: rtc-pcf85063");
