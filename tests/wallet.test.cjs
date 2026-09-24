const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('release/public/app.js','utf8');
function setup(request) {
 const elements = new Map();
 const el = id => { if (!elements.has(id)) elements.set(id,{textContent:'',hidden:true,value:'',disabled:false,listeners:{},addEventListener(k,v){this.listeners[k]=v;}});return elements.get(id); };
 const handlers={};
 const storage=new Map();
 const context={document:{documentElement:{lang:''},getElementById:el,querySelectorAll:()=>[]},window:{navigator:{language:'zh-CN'},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},ethereum:{request,on:(k,v)=>handlers[k]=v}},fetch:async()=>({json:async()=>({verified:false,transactionsEnabled:false})})};
 vm.runInNewContext(code,context);return {el,handlers};
}
const address='0x'+'a'.repeat(40);
test('connect, account details and local logout',async()=>{
 const x=setup(async({method})=>method==='eth_chainId'?'0xaa36a7':[address]);
 await x.el('connect').listeners.click();assert.match(x.el('connect').textContent,/0xaaaa/);
 await x.el('connect').listeners.click();assert.equal(x.el('wallet-panel').hidden,false);
 x.el('disconnect').listeners.click();assert.equal(x.el('connect').textContent,'连接钱包');
});
test('account changes invalidate delayed request',async()=>{
 let resolve;const x=setup(({method})=>method==='eth_requestAccounts'?new Promise(r=>resolve=r):Promise.resolve('0xaa36a7'));
 const pending=x.el('connect').listeners.click();x.handlers.accountsChanged([]);resolve([address]);await pending;
 assert.equal(x.el('connect').textContent,'连接钱包');
});
test('wrong network rejects account session',async()=>{
 const x=setup(async({method})=>method==='eth_chainId'?'0x1':[address]);await x.el('connect').listeners.click();
 assert.equal(x.el('connect').textContent,'连接钱包');assert.match(x.el('wallet-status').textContent,/网络不匹配/);
});
test('duplicate requests suppressed and rejected authorization recovers',async()=>{
 let calls=0,reject;const x=setup(()=>{calls++;return new Promise((a,b)=>reject=b);});
 const pending=x.el('connect').listeners.click();await x.el('connect').listeners.click();assert.equal(calls,1);
 reject({code:4001});await pending;assert.equal(x.el('connect').disabled,false);assert.match(x.el('wallet-status').textContent,/已拒绝/);
});
test('chain switch clears connected account',async()=>{
 const x=setup(async({method})=>method==='eth_chainId'?'0xaa36a7':[address]);await x.el('connect').listeners.click();
 x.handlers.chainChanged('0x1');assert.equal(x.el('connect').textContent,'连接钱包');assert.equal(x.el('account').textContent,'');
});
test('language toggle persists selection without changing wallet session',async()=>{
 const x=setup(async({method})=>method==='eth_chainId'?'0xaa36a7':[address]);
 await x.el('connect').listeners.click();const before=x.el('connect').textContent;
 x.el('locale').listeners.click();assert.equal(x.el('connect').textContent,before);assert.equal(x.el('locale').textContent,'简体中文');
});
