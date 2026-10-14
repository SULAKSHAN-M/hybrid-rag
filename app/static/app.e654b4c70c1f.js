let savedChats=[];
const $=id=>document.getElementById(id);
let currentChat=null, collections=[], busy=false, pollTimer=null, uploadFile=null, uploading=false;
function el(tag,text,parent,cls){const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;if(parent)parent.append(node);return node;}
async function api(path,options={}){const response=await fetch(path,{...options,headers:{'X-Requested-With':'SourceDesk',...(options.headers||{})}});let data;try{data=await response.json();}catch{throw new Error('Server could not complete the request. Check the terminal and try again.');}if(!response.ok){if(response.status===401&&path!='/api/login')showAuth();throw new Error(typeof data.detail==='string'?data.detail:'Check your input and try again.');}return data;}
function json(method,data){return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)};}
function showAuth(){clearTimeout(uploadNoticeTimer);clearTimeout(jobDismissTimer);jobSnapshot=[];completedJobs.clear();uploadFile=null;$('file').value='';updateUploadState();$('auth').hidden=false;$('workspace').hidden=true;$('logout').hidden=true;$('usageButton').hidden=true;$('identity').textContent='';if(pollTimer)clearTimeout(pollTimer);pollTimer=null;currentChat=null;$('turns').replaceChildren();$('preview').close();$('dashboard').close();$('renameDialog').close();$('searchDialog').close();$('documentsDialog').close();savedChats=[];$('recentChats').replaceChildren();}
async function enter(){const me=await api('/api/me');$('auth').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;$('usageButton').hidden=false;$('identity').textContent=me.username;$('password').value='';await refreshCollections();await refreshChats();newConversation();await refreshDocs();await pollJobs();$('status').textContent='';}
async function authenticate(path){$('authStatus').textContent='Please wait…';try{await api(path,json('POST',{username:$('username').value,password:$('password').value}));$('authStatus').textContent='';await enter();}catch(e){$('authStatus').textContent=e.message;}}
$('authForm').onsubmit=e=>{e.preventDefault();authenticate('/api/login');};$('register').onclick=()=>{if($('authForm').reportValidity())authenticate('/api/register');};$('logout').onclick=async()=>{try{await api('/api/logout',{method:'POST'});showAuth();}catch(e){$('status').textContent=e.message;}};
async function refreshCollections(){collections=await api('/api/collections');const selected=$('collection').value;$('collection').replaceChildren();el('option','All collections',$('collection')).value='';for(const c of collections)el('option',c.name,$('collection')).value=c.id;$('collection').value=collections.some(c=>c.id===selected)?selected:(collections[0]?.id||'');updateUploadState();renderProjects();}
$('collectionForm').onsubmit=async e=>{e.preventDefault();try{const c=await api('/api/collections',json('POST',{name:$('collectionName').value}));await refreshCollections();$('collection').value=c.id;updateUploadState();$('collectionName').value='';await refreshDocs();newConversation();renderProjects();}catch(err){$('uploadStatus').textContent=err.message;}};
$('collection').onchange=async()=>{updateUploadState();try{await refreshDocs();newConversation();renderProjects();}catch(e){$('uploadStatus').textContent=e.message;}};
async function refreshDocs(){const docs=await api('/api/documents?folder='+encodeURIComponent($('collection').value));$('documents').replaceChildren();if(!docs.length)el('p','No documents in this view.',$('documents'),'muted');for(const d of docs){const row=el('div','',$('documents'),'doc');el('strong',d.name,row);el('small',`${d.status} · ${d.chunks} passages`,row);const button=el('button','Remove',row,'quiet');button.disabled=d.status==='processing';button.onclick=async()=>{if(!confirm(`Remove ${d.name}? Saved chats retain quoted text; its page previews will become unavailable.`))return;try{await api('/api/documents/'+d.id,{method:'DELETE'});await refreshDocs();}catch(e){$('uploadStatus').textContent=e.message;}};}}
function updateUploadState(){
 const folder=collections.find(c=>c.id===$('collection').value);
 $('uploadCollection').textContent=folder?folder.name:'Select a collection';
 $('uploadCollection').title=folder?folder.name:'Select a collection before uploading';
 $('logout').disabled=uploading||busy;
 $('uploadButton').disabled=uploading||!uploadFile||!folder;
 $('uploadButton').textContent=uploading?'Uploading…':!folder?'Select a collection':uploadFile?'Upload & index document':'Choose a file to upload';
 $('file').disabled=uploading;$('removeFile').disabled=uploading;$('ocr').disabled=uploading;
 $('dropzone').classList.toggle('uploading',uploading);
 $('selectedFile').hidden=!uploadFile;
 if(uploadFile){$('fileName').textContent=uploadFile.name;$('fileName').title=uploadFile.name;$('fileType').textContent=uploadFile.name.split('.').pop().toUpperCase().slice(0,5);$('fileSize').textContent=(uploadFile.size>=1024*1024?(uploadFile.size/(1024*1024)).toFixed(2)+' MB':Math.max(1,Math.ceil(uploadFile.size/1024))+' KB')+' · Ready to upload';}
}
let uploadNoticeTimer=null, jobDismissTimer=null, jobSnapshot=[];
const completedJobs=new Map();
function clearUploadNotice(){clearTimeout(uploadNoticeTimer);uploadNoticeTimer=null;$('transferProgress').hidden=true;$('uploadStatus').textContent='';}
function selectUpload(file){
 if(uploading)return;
 if(!file)return;
 const ext=file.name.split('.').pop().toLowerCase();
 if(!['pdf','docx','txt','md','png','jpg','jpeg','tiff','bmp'].includes(ext)){$('uploadStatus').textContent='Choose a PDF, Word, text or supported image file.';$('file').value='';return;}
 if(file.size>10*1024*1024){$('uploadStatus').textContent='This file is too large. The maximum size is 10 MB.';$('file').value='';return;}
 if(!file.size){$('uploadStatus').textContent='This file is empty. Choose another document.';$('file').value='';return;}
 clearUploadNotice();uploadFile=file;updateUploadState();
}
$('file').onchange=()=>selectUpload($('file').files[0]);
$('removeFile').onclick=()=>{if(uploading)return;uploadFile=null;$('file').value='';$('uploadStatus').textContent='';$('transferProgress').hidden=true;updateUploadState();$('file').focus();};
let dragDepth=0;
$('dropzone').addEventListener('dragenter',event=>{event.preventDefault();if(!uploading){dragDepth++;$('dropzone').classList.add('drag-over');}});
$('dropzone').addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect=uploading?'none':'copy';});
$('dropzone').addEventListener('dragleave',event=>{event.preventDefault();dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)$('dropzone').classList.remove('drag-over');});
$('dropzone').addEventListener('drop',event=>{event.preventDefault();dragDepth=0;$('dropzone').classList.remove('drag-over');if(uploading)return;if(event.dataTransfer.files.length!==1){$('uploadStatus').textContent='Please drop one document at a time.';return;}selectUpload(event.dataTransfer.files[0]);});
$('upload').onsubmit=event=>{
 event.preventDefault();const file=uploadFile,folder=$('collection').value;
 if(uploading)return;if(!folder){$('uploadStatus').textContent='Select a collection for the upload.';return;}if(!file)return;
 const form=new FormData();form.append('file',file);form.append('folder',folder);form.append('ocr',$('ocr').checked);
 clearUploadNotice();uploading=true;updateUploadState();$('uploadStatus').textContent='Preparing upload…';$('transferProgress').hidden=false;$('transferProgress').value=0;
 const xhr=new XMLHttpRequest();xhr.open('POST','/api/documents');xhr.setRequestHeader('X-Requested-With','SourceDesk');
 xhr.upload.onprogress=e=>{if(e.lengthComputable){const percentage=Math.round(e.loaded/e.total*100);$('transferProgress').value=percentage;$('uploadStatus').textContent=percentage===100?'Upload complete. Waiting for indexing to start…':`Uploading ${percentage}%`;}};
 xhr.onload=async()=>{uploading=false;try{const result=JSON.parse(xhr.responseText);if(xhr.status>=400)throw new Error(typeof result.detail==='string'?result.detail:'Upload failed.');$('uploadStatus').textContent='Document uploaded. Indexing progress appears below.';uploadFile=null;$('file').value='';$('transferProgress').value=100;uploadNoticeTimer=setTimeout(clearUploadNotice,3000);await refreshDocs();await pollJobs();}catch(error){$('uploadStatus').textContent=error.message;$('transferProgress').hidden=true;}finally{updateUploadState();}};
 xhr.onerror=()=>{uploading=false;updateUploadState();$('transferProgress').hidden=true;$('uploadStatus').textContent='Connection interrupted. Check the document list before retrying.';};xhr.send(form);
};
function renderJobs(){
 clearTimeout(jobDismissTimer);jobDismissTimer=null;
 const now=Date.now();let nextExpiry=Infinity;
 $('jobs').replaceChildren();
 const visible=jobSnapshot.filter(j=>{
  if(j.stage!=='done')return true;
  if(!completedJobs.has(j.id))completedJobs.set(j.id,now+3000);
  const expires=completedJobs.get(j.id);
  if(expires<=now)return false;
  nextExpiry=Math.min(nextExpiry,expires);return true;
 });
 for(const j of visible.slice(0,5)){
  const row=el('div','',$('jobs'),'job');
  const label=j.stage==='done'?'Document indexed':j.stage==='failed'?'Indexing failed':j.stage==='queued'?'Waiting to index':j.stage.charAt(0).toUpperCase()+j.stage.slice(1);
  const line=el('div','',row,'job-heading');el('span',label,line);el('span',j.stage==='failed'?'':`${j.progress}%`,line);
  if(j.error)el('small',j.error,row);
  const bar=el('progress','',row);bar.max=100;bar.value=j.progress;bar.setAttribute('aria-label',label+' progress');
 }
 if(nextExpiry!==Infinity)jobDismissTimer=setTimeout(renderJobs,Math.max(0,nextExpiry-Date.now()));
}
async function pollJobs(){
 if(pollTimer)clearTimeout(pollTimer);pollTimer=null;if($('workspace').hidden)return;
 try{
  const jobs=await api('/api/jobs');if($('workspace').hidden)return;
  jobSnapshot=jobs;renderJobs();await refreshDocs();
  if(jobs.some(j=>!['done','failed'].includes(j.stage)))pollTimer=setTimeout(pollJobs,1500);
 }catch(e){$('uploadStatus').textContent=e.message;}
}
async function refreshChats(){const chats=await api('/api/chats');savedChats=chats;$('chatList').replaceChildren();el('option','New conversation',$('chatList')).value='';for(const c of chats)el('option',c.title,$('chatList')).value=c.id;$('chatList').value=currentChat||'';renderRecentChats();}
function setExports(){$('exportDocx').hidden=$('exportPdf').hidden=!currentChat;$('deleteChat').disabled=!currentChat||busy;$('renameChat').disabled=!currentChat||busy;if(currentChat){$('exportDocx').href=`/api/chats/${currentChat}/export/docx`;$('exportPdf').href=`/api/chats/${currentChat}/export/pdf`;}}
function newConversation(){if(busy)return;document.querySelector('.conversation').classList.add('is-new');$('centralUpload').open=true;currentChat=null;$('chatList').value='';$('chatTitle').textContent='Ask your documents.';$('scope').textContent='Scope: '+(collections.find(c=>c.id===$('collection').value)?.name||'All collections');$('turns').replaceChildren();showWelcome();setExports();renderRecentChats();}
$('newChat').onclick=newConversation;
$('chatList').onchange=async()=>{if(busy)return;if(!$('chatList').value){newConversation();return;}try{currentChat=$('chatList').value;document.querySelector('.conversation').classList.remove('is-new');$('centralUpload').open=false;const chat=await api('/api/chats/'+currentChat);$('chatTitle').textContent=chat.title;$('scope').textContent='Scope: '+(collections.find(c=>c.id===chat.folder)?.name||'All collections');$('turns').replaceChildren();for(const turn of chat.turns)renderTurn(turn);setExports();renderRecentChats();}catch(e){$('status').textContent=e.message;}};
$('deleteChat').onclick=async()=>{if(!currentChat||!confirm('Delete this conversation and its feedback? Aggregate usage records will remain.'))return;try{await api('/api/chats/'+currentChat,{method:'DELETE'});newConversation();await refreshChats();}catch(e){$('status').textContent=e.message;}};
function setBusy(value){busy=value;for(const id of ['askButton','newChat','chatList','collection','deleteChat','logout','collectionName'])$(id).disabled=value;$('logout').disabled=value||uploading;setExports();}
$('ask').onsubmit=async e=>{e.preventDefault();if(busy)return;const question=$('question').value.trim();if(question.length<2)return;document.querySelector('.conversation').classList.remove('is-new');$('centralUpload').open=false;setBusy(true);$('turns').setAttribute('aria-busy','true');$('status').textContent='Searching your documents and checking supporting evidence…';try{if(!currentChat){const created=await api('/api/chats',json('POST',{folder:$('collection').value||null}));currentChat=created.id;$('turns').replaceChildren();$('chatTitle').textContent=question.slice(0,70);$('scope').textContent='Scope: '+(collections.find(c=>c.id===$('collection').value)?.name||'All collections');}const turn=await api('/api/ask',json('POST',{chat_id:currentChat,question}));renderTurn(turn);$('turns').scrollTop=$('turns').scrollHeight;$('question').value='';resizeQuestion();$('status').textContent='Saved. You can ask a follow-up question.';await refreshChats();}catch(err){$('status').textContent=err.message;}finally{setBusy(false);$('turns').setAttribute('aria-busy','false');}};
function renderTurn(turn){const result=turn.result;const box=el('article','',$('turns'),'turn');el('h3',turn.question,box,'user-message');el('div','SourceDesk',box,'answer-label');el('p',result.message,box,'message');const lookup=new Map(result.sources.map((s,i)=>[s.id,{...s,index:i+1}]));for(const claim of result.claims){el('p',claim.statement,box,'claim');const s=lookup.get(claim.source_id);if(s){const button=el('button',`[${s.index}] ${s.name} · page/section ${s.page}`,box,'citation');button.onclick=()=>openSource(s.id);}el('blockquote',claim.quote,box);}const evidence=el('section','',box,'evidence-panel');evidence.setAttribute('aria-label','Retrieved evidence');el('h4',`Retrieved evidence (${result.sources.length})`,evidence);if(!result.sources.length)el('p','No source passages were retrieved for this question.',evidence);for(const source of result.sources){const button=el('button',`${source.name} · page/section ${source.page}`,evidence,'citation');button.onclick=()=>openSource(source.id);el('p',source.text,evidence);el('small',`Relevance score ${source.rerank_score} · not a confidence percentage`,evidence);}const meta=[result.model||'Document search',`${result.latency_seconds||0}s`,result.fallback_used?'Fallback used':''];el('small',meta.filter(Boolean).join(' · '),box);const feedback=el('div','',box,'feedback');const note=el('input','',feedback);note.placeholder='Optional feedback';note.maxLength=1000;note.setAttribute('aria-label','Feedback note');const status=el('span','',feedback);for(const [label,rating]of [['Helpful',1],['Incorrect / irrelevant',-1]]){const button=el('button',label,feedback,'quiet');button.onclick=async()=>{try{await api(`/api/turns/${turn.id}/feedback`,json('POST',{rating,note:note.value}));status.textContent='Feedback saved';}catch(e){status.textContent=e.message;}};}}
async function openSource(id){$('preview').showModal();$('previewTitle').textContent='Loading source…';$('previewText').textContent='';$('previewImage').hidden=true;$('previewImage').removeAttribute('src');$('previewInfo').textContent='';try{const source=await api('/api/sources/'+id);$('previewTitle').textContent=`${source.name} · page/section ${source.page}`;$('previewText').textContent=source.text;$('previewInfo').textContent=source.visual?'The retrieved passage is highlighted below. OCR text may contain recognition errors.':'Extracted source passage';if(source.preview_url){$('previewImage').src=source.preview_url;$('previewImage').hidden=false;}}catch(e){$('previewTitle').textContent='Source unavailable';$('previewInfo').textContent=e.message;}}
$('closePreview').onclick=()=>$('preview').close();$('closeUsage').onclick=()=>$('dashboard').close();
$('usageButton').onclick=async()=>{$('dashboard').showModal();$('usageContent').replaceChildren();try{const data=await api('/api/usage');const list=el('dl','',$('usageContent'),'metrics');for(const [label,value]of [['Questions',data.summary.requests],['Average response time',data.summary.average_seconds.toFixed(2)+'s'],['Reported tokens',data.summary.reported_tokens],['Fallback attempts',data.summary.fallback_attempts],['Calls without token totals',data.summary.unreported_requests]]){el('dt',label,list);el('dd',String(value),list);}el('p',data.token_note,$('usageContent'));const table=el('table','',$('usageContent'));const head=el('tr','',el('thead','',table));for(const h of ['Model','Questions','Tokens'])el('th',h,head);const body=el('tbody','',table);for(const model of data.models){const row=el('tr','',body);for(const value of [model.model,model.requests,model.tokens??'Not reported'])el('td',String(value),row);}el('h3','Recent requests',$('usageContent'));for(const row of data.recent)el('p',`${row.status} · ${row.model||'Search only'} · ${row.latency}s · ${row.attempts} attempts`,$('usageContent'));}catch(e){el('p',e.message,$('usageContent'));}};
enter().catch(()=>showAuth());

function resizeQuestion(){const field=$('question');$('questionCount').textContent=`${field.value.length} / 1500`;field.rows=Math.min(6,Math.max(2,field.value.split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/Math.max(20,Math.floor(field.clientWidth/8)))),0)));}
$('question').addEventListener('input',resizeQuestion);
$('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&event.keyCode!==229){event.preventDefault();if(!busy&&$('question').value.trim().length>=2)$('ask').requestSubmit();}});

let renameTarget=null;
$('renameChat').onclick=()=>{if(!currentChat||busy)return;renameTarget=currentChat;$('conversationName').value=$('chatTitle').textContent;$('renameStatus').textContent='';$('renameDialog').showModal();$('conversationName').focus();$('conversationName').select();};
$('closeRename').onclick=$('cancelRename').onclick=()=>$('renameDialog').close();
$('renameForm').onsubmit=async event=>{event.preventDefault();const name=$('conversationName').value.trim();if(!name){$('renameStatus').textContent='Enter a conversation name.';return;}if(!renameTarget)return;$('saveRename').disabled=true;try{const updated=await api('/api/chats/'+renameTarget,json('PATCH',{name}));if(currentChat===updated.id)$('chatTitle').textContent=updated.title;await refreshChats();$('renameDialog').close();}catch(error){$('renameStatus').textContent=error.message;}finally{$('saveRename').disabled=false;}};

const welcomeTemplate=$('turns').querySelector('.empty-state')?.cloneNode(true);
function wireStarters(){for(const button of $('turns').querySelectorAll('[data-prompt]'))button.onclick=()=>{$('question').value=button.dataset.prompt;resizeQuestion();$('question').focus();};}
function showWelcome(){if(welcomeTemplate){$('turns').append(welcomeTemplate.cloneNode(true));wireStarters();}}
wireStarters();
$('toggleLibrary').onclick=()=>setSidebar(!sidebarIsOpen());

const helpContent={
 features:['Everything in your workspace','Organize files into collections, search document text and ask follow-up questions in saved conversations. Open citations to check supporting passages, rename conversations, leave answer feedback and export chats to Word or PDF.','Scanned pages can be processed with OCR when Tesseract is installed. The Usage panel shows response times, model activity and reported token totals.'],
 formats:['Supported documents','Upload PDF, DOCX, TXT, MD, PNG, JPG, JPEG, TIFF or BMP files, one at a time, up to 10 MB each. Choose a collection before uploading.','Wait until the document is marked ready before asking questions about it. Scanned PDFs and images may take longer because text must be recognized first.'],
 exports:['Take your conversations with you','Open a saved conversation and use Download Word or Download PDF above the messages. Exports include the saved answers and source references.'],
 guide:['Get started with SourceDesk','1. Sign in or create an account. Choose a collection, or add one for your project.','2. Upload a document and wait until it is ready.','3. Ask a question. Press Enter to send or Shift + Enter for a new line.','4. Open a citation to review the source. Your saved conversation is available in Recents in the sidebar.'],
 faq:['Frequently asked questions','Why is my upload taking time? The first upload can load or download search models. Larger files, scanned pages and local computer performance also affect processing time.','Why is there no answer? Your documents may not contain enough relevant evidence, processing may still be running, or the configured AI provider may be unavailable.','Can I continue a conversation? Select it from Recents in the sidebar and ask a follow-up question.','Can I rename a conversation? Open the conversation, choose Rename and save the new name.'],
 citations:['Check the source behind an answer','Select a source citation to open its passage. Supported PDF and image previews highlight the retrieved passage so you can compare the answer with the document.','A citation links to retrieved evidence; it does not guarantee that every interpretation is correct. Review the original passage when accuracy matters.'],
 ocr:['Read scanned documents','Keep Read scanned documents enabled for image files and PDFs without selectable text. OCR needs Tesseract installed and configured on the server.','Clear scans give better results. OCR can misread characters, especially in low-resolution images, complex tables or handwriting.'],
 privacy:['Privacy & data','This installation stores accounts, uploaded documents, extracted text, search indexes, conversations, feedback and usage records on the computer or server running SourceDesk.','When AI answers are enabled, your question, recent conversation context and retrieved excerpts are sent to the configured AI provider. That provider’s data handling terms also apply.','Removing a document removes it from active document search. Existing conversations and exports can retain quoted text. This notice describes the app’s current behavior; deployment-specific policies are provided by the installation operator.'],
 security:['Security information','Documents and conversations are scoped to signed-in accounts. Passwords are hashed and sign-in sessions use an HttpOnly cookie.','The default localhost address uses HTTP. A public deployment needs HTTPS and appropriate server configuration. This application does not claim security certification or an independent security audit.'],
 cookies:['Cookies','SourceDesk uses an essential session cookie to keep you signed in. Signing out ends your current session.','The application does not include advertising or analytics cookies. Hosting services added by an operator may have their own policies.'],
 ai:['About AI answers','SourceDesk retrieves relevant document passages and uses the configured AI provider to prepare supported answers. Model selection is automatic.','AI answers and OCR can contain mistakes. Check cited passages before relying on important information. If evidence is insufficient, try a more specific question or add a relevant document.']
};
for(const button of document.querySelectorAll('[data-info]'))button.onclick=()=>{const [title,...paragraphs]=helpContent[button.dataset.info];$('infoTitle').textContent=title;$('infoBody').replaceChildren();for(const paragraph of paragraphs)el('p',paragraph,$('infoBody'));$('infoDialog').showModal();};
$('closeInfo').onclick=()=>$('infoDialog').close();
for(const button of document.querySelectorAll('[data-workspace]'))button.onclick=()=>{const signedIn=!$('workspace').hidden;(signedIn?$('workspace'):$('auth')).scrollIntoView({block:'start'});(signedIn?$('question'):$('username')).focus({preventScroll:true});};
$('copyrightYear').textContent=String(new Date().getFullYear());

function sidebarIsOpen(){return window.matchMedia('(max-width:720px)').matches?$('workspace').classList.contains('sidebar-open'):!$('workspace').classList.contains('sidebar-collapsed');}
function setSidebar(open){$('workspace').classList.toggle('sidebar-open',open);$('workspace').classList.toggle('sidebar-collapsed',!open);$('toggleLibrary').setAttribute('aria-expanded',String(open));if(!open)$('toggleLibrary').focus();}
$('toggleLibrary').setAttribute('aria-expanded',String(sidebarIsOpen()));
$('collapseSidebar').onclick=()=>setSidebar(false);
$('sidebarNewChat').onclick=()=>{if(busy)return;newConversation();$('question').focus();};
$('attachDocument').onclick=()=>{$('centralUpload').open=true;$('centralUpload').scrollIntoView({block:'nearest'});$('file').focus();};
$('openDocuments').onclick=async()=>{try{await refreshDocs();$('documentsDialog').showModal();}catch(e){$('status').textContent=e.message;}};
$('closeDocuments').onclick=()=>$('documentsDialog').close();
function renderProjects(){
 $('pinnedProjects').replaceChildren();$('projectList').replaceChildren();
 for(const project of collections){
  const row=el('div','',project.pinned?$('pinnedProjects'):$('projectList'),'project-row');
  const button=el('button',project.name,row,'project-select');button.type='button';button.title=project.name;button.classList.toggle('selected',project.id===$('collection').value);
  button.onclick=async()=>{if(busy)return;$('collection').value=project.id;await $('collection').onchange();renderProjects();};
  const pin=el('button',project.pinned?'★':'☆',row,'pin-project');pin.type='button';pin.title=(project.pinned?'Unpin ':'Pin ')+project.name;pin.setAttribute('aria-label',pin.title);pin.setAttribute('aria-pressed',String(Boolean(project.pinned)));
  pin.onclick=async()=>{pin.disabled=true;try{await api('/api/collections/'+project.id+'/pin',json('PATCH',{pinned:!project.pinned}));await refreshCollections();}catch(e){$('status').textContent=e.message;pin.disabled=false;}};
 }
 if(!collections.some(p=>p.pinned))el('p','Pin a project with ☆ to keep it here.',$('pinnedProjects'),'sidebar-empty');
}
async function openSavedChat(id){if(busy)return;$('chatList').value=id;await $('chatList').onchange();if(window.matchMedia('(max-width:720px)').matches)setSidebar(false);}
function renderRecentChats(){
 $('recentChats').replaceChildren();
 for(const chat of savedChats){const button=el('button',chat.title,$('recentChats'),'recent-chat');button.type='button';button.title=chat.title;button.classList.toggle('selected',chat.id===currentChat);button.onclick=()=>openSavedChat(chat.id);}
 if(!savedChats.length)el('p','Your conversations will appear here.',$('recentChats'),'sidebar-empty');
}
function searchConversations(){
 const query=$('chatSearchInput').value.trim().toLocaleLowerCase();$('chatSearchResults').replaceChildren();
 const results=savedChats.filter(chat=>chat.title.toLocaleLowerCase().includes(query));
 for(const chat of results){const button=el('button',chat.title,$('chatSearchResults'),'search-result');button.type='button';button.onclick=()=>{if(busy)return;$('searchDialog').close();openSavedChat(chat.id);};}
 if(!results.length)el('p','No matching conversations.',$('chatSearchResults'));
}
$('searchChats').onclick=()=>{$('chatSearchInput').value='';searchConversations();$('searchDialog').showModal();$('chatSearchInput').focus();};
$('closeSearch').onclick=()=>$('searchDialog').close();$('chatSearchInput').oninput=searchConversations;

function updateThemeControl(){const dark=document.documentElement.dataset.theme==='dark';$('themeIcon').textContent=dark?'☀':'☾';$('themeLabel').textContent=dark?'Light':'Dark';const label='Switch to '+(dark?'light':'dark')+' theme';$('themeToggle').setAttribute('aria-label',label);$('themeToggle').title=label;}
$('themeToggle').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;try{localStorage.setItem('sourcedesk-theme',theme);}catch{}updateThemeControl();};
updateThemeControl();
