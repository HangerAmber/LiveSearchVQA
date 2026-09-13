// Offline logic checks only; this does not claim browser rendering coverage.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
async function test(name){
 const html=fs.readFileSync(path.join(root,name),'utf8');
 const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
 assert(!/__SNAPSHOT_META__|__DATA__|__CURRENT_JSON__/.test(script));
 const nodes=new Map();
 const node=id=>{if(!nodes.has(id))nodes.set(id,{id,dataset:{},style:{},innerHTML:'',textContent:'',value:'',
    querySelectorAll:()=>[],classList:{add(){},remove(){},toggle(){}}});return nodes.get(id)};
 const context=vm.createContext({document:{getElementById:node,querySelectorAll:()=>[],addEventListener(){}},
   IntersectionObserver:class{observe(){} unobserve(){}},requestAnimationFrame:fn=>fn(2000),
   URL,URLSearchParams,location:{href:'http://localhost/'+name,search:''},history:{replaceState(){}},
   fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,url),'utf8'))}),console});
 vm.runInContext(script,context,{timeout:5000});
 const initial=vm.runInContext('({n:DATA.length,date:selectedDate,preview:IS_PREVIEW})',context);
 assert.equal(initial.n,initial.preview?121:171);
 vm.runInContext('revealAns()',context);
 assert.equal(node('c-ans').style.display,'block');
 assert.equal((node('c-cb').innerHTML.match(/class="chip /g)||[]).length,12);
 assert.equal((node('c-or').innerHTML.match(/class="chip /g)||[]).length,12);
 for(const [date,n] of [['2026-08-15',200],['2026-08-18',171]]){
   await vm.runInContext(`switchBuild('${date}')`,context);
   assert.equal(node('count').textContent,`${n} / ${n} items`);
   const expected=date===initial.date?'data/benchmark_v2.json':`data/archive_v2/${date}.json`;
   assert.equal(node('download-split').href,expected);
 }
 if(initial.preview){
   await vm.runInContext('switchBuild(CURRENT_DATE)',context);
   assert.equal(node('download-split').href,'data/previews/2026-09-05.json');
   assert.equal(node('count').textContent,'121 / 121 items');
 }else{
   await vm.runInContext("switchBuild('2026-09-05')",context);
   assert.equal(context.location.href,'preview.html');
 }
 console.log(name+': English snapshots, exact counts, panel display, and same-artifact downloads PASS');
}
(async()=>{for(const name of ['index.html','index_v2.html','demo.html','preview.html'])await test(name)})()
 .catch(e=>{console.error(e);process.exitCode=1});
