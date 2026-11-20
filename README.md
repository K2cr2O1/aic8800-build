# AIC8800DC 驱动编译（GitHub Actions）

为 **kwrt 25.12-SNAPSHOT / kernel 6.12.116 / x86_64** 编译绿联 CM760/AX300（AIC8800DC）USB 网卡驱动。

## 为什么是这个组合

实测路由器内核的要求：

```
vermagic = 6.12.116 SMP mod_unload
__versions 节 = 不存在  →  CONFIG_MODVERSIONS = OFF
```

- 内核**不校验符号 CRC**，只比对 vermagic 字符串 → 门槛比发行版低得多
- 官方 `snapshots` 已升到 6.18.x，ABI 不兼容，**不能用**
- 官方 `25.12.0` 正式版是 **6.12.71**，同分支，patch 号差异不影响结构体布局 → **用这个**

## 使用步骤

**1. 建仓库并推送**

```bash
mkdir aic8800-build && cd aic8800-build
git init -b main
mkdir -p .github/workflows
# 把 build-aic8800.yml 放到 .github/workflows/
git add -A && git commit -m "build aic8800 for kwrt 6.12.116"
git remote add origin git@github.com:<你的账号>/aic8800-build.git
git push -u origin main
```

**2. 跑 Action**

仓库页面 → Actions → `build-aic8800dc-x86_64` → Run workflow。
约 15–25 分钟（SDK 296 MB + 全量 feeds）。

**3. 下载产物**

运行完成后的 Artifacts 里有：
- `kmod-aic8800dc_*.ipk`
- `aic_load_fw.ko`、`aic8800_fdrv.ko`
- `a69c-5722`（usbmode 数据）
- 日志里会打印实际 vermagic，**先看一眼是否是 `6.12.71`**

## 路由器侧安装

**关键：不要用 `opkg install` 装 ipk**。ipk 里写着 `Depends: kernel (= 6.12.71~...)`，你的内核是 6.12.116，opkg 会直接拒绝。手动放 ko 更省事：

```sh
# 1. 上传 ko 到 /tmp，然后
mkdir -p /lib/modules/6.12.116/extra
cp /tmp/aic_load_fw.ko /tmp/aic8800_fdrv.ko /lib/modules/6.12.116/extra/

# 2. 尝试加载（-f 强制忽略 vermagic）
insmod /lib/modules/6.12.116/extra/aic_load_fw.ko
insmod /lib/modules/6.12.116/extra/aic8800_fdrv.ko

# 若报 version magic 不匹配，用 busybox 的强制模式：
insmod -f /lib/modules/6.12.116/extra/aic8800_fdrv.ko

# 3. 确认
dmesg | grep -i aic
lsmod | grep aic
```

## 模式切换（光盘 → 网卡）

设备插上时是 `a69c:5722`（伪装成只读 U 盘，里面有 `ugreen_wifi_driver.exe`），必须切到 `a69c:88de` 才会出现网卡。

```sh
# 先确认 usb_modeswitch 二进制存在（本机目前只有 hotplug 钩子，没有二进制）
ls -l /usr/sbin/usb_modeswitch /usr/bin/usb_modeswitch

# 不存在就重装
opkg update && opkg install --force-reinstall usb-modeswitch

# 切换
usb_modeswitch -v a69c -p 5722 -K
sleep 3
cat /sys/kernel/debug/usb/devices | grep -A2 a69c
```

切换成功后 `dmesg` 会出现 `aic8800` 相关日志，`ip link` 里出现 `wlan1`（或 `phy1`）。

## 加到无线配置

驱动起来后，让 OpenWrt 自动生成第二块 radio：

```sh
wifi config          # 生成 radio1 / default_radio1
uci set wireless.radio1.band='2g'
uci set wireless.radio1.channel='6'
uci set wireless.radio1.htmode='HT20'
uci set wireless.radio1.disabled='0'
uci set wireless.default_radio1.ssid='DOGSOHA-2.4G'
uci set wireless.default_radio1.encryption='psk2+ccmp'
uci set wireless.default_radio1.key='你的密码'
uci set wireless.default_radio1.network='lan'
uci commit wireless
wifi reload
```

## 失败时的排查顺序

| 现象 | 原因 | 处理 |
|---|---|---|
| `make` 报 cfg80211 结构体不匹配 | 缺 NOSTDINC_FLAGS backport 段 | 包仓库里已含补丁；若报错，按 CSDN 那篇加 `-I$(STAGING_DIR)/usr/include/mac80211-backport` 等 |
| `insmod` 报 `version magic` | vermagic 不一致 | `insmod -f`，或改 SDK 的 kernel Makefile SUBLEVEL 后重编 |
| `insmod` 报 `Unknown symbol` | 内核 ABI 差异过大 | 换 24.10（6.6）固件重来，或放弃 |
| 加载成功但无 `wlan` | 模式没切过去 | 回到「模式切换」步骤 |
| 有 `wlan` 但扫不到 | 驱动 AP 模式限制 | 看 `iw phy phy1 info` 是否支持 `AP` |

## 备注

- 该驱动是 GPL-3.0 的厂商驱动改写，来源与补丁见 `kasonhaimen/openwrt-aic8800dc` 的 `THIRD_PARTY.md`
- 每次升级路由器固件（内核变化）都要重编一次，把 kernel 版本对上
