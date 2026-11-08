import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const directories=['web','assets','fonts'].map(name=>path.join(root,name)+path.sep);
const index=path.join(root,'index.html');
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
  '.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8',
  '.png':'image/png','.svg':'image/svg+xml','.jpg':'image/jpeg','.ttf':'font/ttf'};
const isPublic=filename=>filename===index||directories.some(directory=>filename.startsWith(directory));

// Serve only the browser game. Python sources, credentials and repository
// metadata are outside these public routes, including through symbolic links.
export function createGameServer(){
  return http.createServer(async(request,response)=>{
    try{
      if(!['GET','HEAD'].includes(request.method)){response.writeHead(405);response.end();return;}
      let pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);
      if(pathname==='/')pathname='/index.html';
      const filename=path.resolve(root,'.'+pathname);
      if(!isPublic(filename)||!mime[path.extname(filename)]||!isPublic(await fs.realpath(filename))){
        response.writeHead(404);response.end();return;
      }
      const data=await fs.readFile(filename);
      response.writeHead(200,{'Content-Type':mime[path.extname(filename)],'Cache-Control':'no-store',
        'X-Content-Type-Options':'nosniff'});
      response.end(request.method==='HEAD'?undefined:data);
    }catch{response.writeHead(404);response.end();}
  });
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const port=Number(process.env.PORT||4173);
  if(!Number.isInteger(port)||port<0||port>65535)throw new Error('PORT must be an integer between 0 and 65535.');
  const server=createGameServer();
  server.on('error',error=>{console.error('Could not start the game preview: '+error.code);process.exitCode=1;});
  server.listen(port,'127.0.0.1',()=>console.log('Marble Race: http://127.0.0.1:'+server.address().port));
}
