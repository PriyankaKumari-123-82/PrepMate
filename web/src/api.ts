const BASE = import.meta.env.VITE_API_URL || '/api'

export type Document = { id:number; title:string; filename:string; page_count:number; status:string; progress:number; error:string|null; created_at:string }
export type Concept = { id:number; name:string; summary:string; chapter:string|null; order_idx:number; mastery:number }
export type Question = { id:number; concept_id:number; type:string; stem:string; options:string[]|null; difficulty:string }
export type Citation = { document_id:number; document_title:string; page:number; quote:string; score:number }

export class ApiError extends Error { constructor(public status:number, message:string){ super(message) } }

async function request<T>(path:string, init:RequestInit = {}):Promise<T> {
  const token = localStorage.getItem('prepmate_token')
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type','application/json')
  const response = await fetch(`${BASE}${path}`, {...init, headers})
  if (!response.ok) {
    let message = response.statusText
    try { message = (await response.json()).detail || message } catch { /* response is not JSON */ }
    throw new ApiError(response.status, message)
  }
  return response.json()
}

export const api = {
  auth: (mode:'login'|'register', email:string, password:string) => request<{access_token:string}>(`/auth/${mode}`, {method:'POST', body:JSON.stringify({email,password})}),
  documents: () => request<Document[]>('/documents'),
  upload: (file:File, title:string) => { const body=new FormData(); body.append('file',file); if(title) body.append('title',title); return request<Document>('/documents',{method:'POST',body}) },
  concepts: (id:number) => request<Concept[]>(`/documents/${id}/concepts`),
  createTest: (documentId:number,count=10) => request<{id:number;mode:string;questions:Question[]}>('/tests',{method:'POST',body:JSON.stringify({mode:'practice',document_ids:[documentId],count})}),
  answer: (attemptId:number,questionId:number,response:string) => request<{correct:boolean;marks:number;answer:string;explanation:string;source_quote:string;page:number}>(`/attempts/${attemptId}/answers`,{method:'POST',body:JSON.stringify({question_id:questionId,response})}),
  submit: (attemptId:number) => request<{score:number;answered:number}>(`/attempts/${attemptId}/submit`,{method:'POST'}),
  dashboard: () => request<{accuracy:number;answers:number;weak_concepts:{id:number;name:string;score:number}[];study_next:string|null}>('/dashboard'),
  chat: (documentIds:number[],message:string) => request<{answer:string;citations:Citation[]}>('/chat',{method:'POST',body:JSON.stringify({document_ids:documentIds,message,k:4})}),
  openPdf: async (id:number,page=1) => { const token=localStorage.getItem('prepmate_token'); const response=await fetch(`${BASE}/documents/${id}/file`,{headers:{Authorization:`Bearer ${token}`}}); if(!response.ok) throw new Error('Could not open PDF'); const url=URL.createObjectURL(await response.blob()); window.open(`${url}#page=${page}`,'_blank') }
}
