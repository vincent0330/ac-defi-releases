'use strict';
const $ = id => document.getElementById(id);
const chain = '0xaa36a7';
let generation = 0, pending = false, account = null;
const wallet = window.ethereum;
function status(text) { $('wallet-status').textContent = text; }
function clearSession() {
  generation++; account = null;
  $('connect').textContent = '连接钱包'; $('wallet-panel').hidden = true;
  $('account').textContent = '';
}
function showAccount(accounts) {
  if (!Array.isArray(accounts) || !/^0x[0-9a-fA-F]{40}$/.test(accounts[0] || '')) {
    clearSession(); status('钱包未授权账户'); return;
  }
  account = accounts[0]; $('connect').textContent = `${account.slice(0,6)}…${account.slice(-4)}`;
  $('account').textContent = account;
}
$('connect').addEventListener('click', async () => {
  if (account) { $('wallet-panel').hidden = !$('wallet-panel').hidden; return; }
  if (!wallet) { status('未检测到钱包扩展。请安装 MetaMask 后刷新页面。'); return; }
  if (pending) return;
  pending = true; const requestGeneration = generation;
  $('connect').disabled = true; status('等待钱包账户授权…');
  try {
    const accounts = await wallet.request({method:'eth_requestAccounts'});
    const network = await wallet.request({method:'eth_chainId'});
    if (requestGeneration !== generation) return;
    if (network.toLowerCase() !== chain) { clearSession(); status('网络不匹配，请在钱包中选择 Ethereum Sepolia，然后重新连接。'); return; }
    showAccount(accounts); status(account ? '账户已连接 · 合约未核验 · 资金操作未开放' : '钱包未授权账户');
  } catch (error) {
    if (requestGeneration === generation) status(error.code === 4001 ? '已拒绝账户授权，可重新连接。' : error.code === -32002 ? '钱包已有待处理请求，请在扩展中完成。' : '钱包连接失败，请检查扩展状态。');
  } finally { pending = false; $('connect').disabled = false; }
});
$('disconnect').addEventListener('click', () => { clearSession(); status('已退出站点。钱包授权请在扩展中管理。'); });
$('network').addEventListener('click', () => status('仅支持 Ethereum Sepolia（11155111）。请在钱包扩展中选择此网络；本站不自动切换网络。'));
if (wallet && wallet.on) {
  wallet.on('accountsChanged', () => { clearSession(); status('钱包账户已改变，请重新连接以确认账户。'); });
  wallet.on('chainChanged', () => { clearSession(); status('钱包网络已改变，请选择 Sepolia 后重新连接。'); });
  wallet.on('disconnect', () => { clearSession(); status('钱包连接已断开。'); });
}
const tabs = {
  deposit:['存入金额','USDC','只读预览，不生成报价或交易。'],
  redeem:['赎回份额','acUSDC','即时退出需要足额可信流动性，不足时整体回滚。当前未开放。'],
  queue:['排队份额','acUSDC','24 小时批次；关闭前可取消未结算份额，预留债权仅可领取。当前未开放。']
};
document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-tab]').forEach(tab => tab.setAttribute('aria-selected', String(tab === button)));
  const [label,unit,help] = tabs[button.dataset.tab];
  $('amount-label').textContent = label; $('amount-unit').textContent = unit;
  $('form-help').textContent = help; $('amount').value = '';
}));
$('amount').addEventListener('input', () => {
  const value = $('amount').value;
  $('form-help').textContent = value && !/^(0|[1-9]\d*)(\.\d{0,6})?$/.test(value)
    ? '请输入最多 6 位小数的非负金额。此处不生成交易。' : '余额与报价不可用，资金操作未开放。';
});
fetch('/api/status').then(r => r.json()).then(data => {
  if (data.verified !== false || data.transactionsEnabled !== false) status('配置状态异常，保持只读。');
}).catch(() => status('服务状态暂不可用，保持只读。'));
