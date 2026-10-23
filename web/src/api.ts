const BASE = import.meta.env.VITE_API_URL || '/api'

export type Document = { id:number; title:string; filename:string; page_count:number; status:string; progress:number; error:string|null; created_at:string }
export type Concept = { id:number; name:string; summary:string; chapter:string|null; order_idx:number; mastery:number }
export type Chunk = { id:number; page_start:number; page_end:number; section:string|null; text:string }
export type Question = { id:number; concept_id:number; type:string; stem:string; options:string[]|null; difficulty:string }
export type Citation = { document_id:number; document_title:string; page:number; quote:string; score:number }
export type Artifact = { id:number; artifact_type:string; title:string; status:string; version:number; body:Record<string,unknown>; sources:{document_id:number;page:number;chunk_id:number;quote:string}[]; warnings:string[]; created_at:string; updated_at:string }
export type Profile = { id:number; email:string; name:string; role:string|null; institution:string|null }
export type ResumeSkill = { name:string; evidence:string[]; confidence:number }
export type ResumeProfile = { summary:string; education:string[]; experience:string[]; projects:string[]; skills:ResumeSkill[]; certifications:string[]; interests:string[] }
export type Resume = { id:number; filename:string; status:string; parsed_profile:Partial<ResumeProfile>; version:number; error:string|null; created_at:string; updated_at:string }
export type CareerGoal = { id:number; target_role:string; experience_level:string; job_description:string|null; interests:string[]; deadline:string|null; weekly_hours:number; created_at:string }
export type PreparationTask = { id:number; skill_id:number|null; title:string; task_type:string; priority:number; reasons:string[]; due_date:string|null; completed:boolean }
export type PreparationPlan = { id:number; goal_id:number; version:number; summary:string; status:string; created_at:string; tasks:PreparationTask[] }

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
  if (response.status === 204) return undefined as T
  return response.json()
}

export const api = {
  auth: (mode:'login'|'register', email:string, password:string, account_type:'student'|'teacher', first_name?:string) => request<{access_token:string}>(`/auth/${mode}`, {method:'POST', body:JSON.stringify({email,password,account_type,first_name:first_name||null})}),
  me: () => request<Profile>('/auth/me'),
  updateProfile: (first_name:string) => request<{first_name:string}>('/auth/me',{method:'PATCH',body:JSON.stringify({first_name})}),
  updatePassword: (current_password:string,new_password:string) => request<{status:string}>('/auth/password',{method:'POST',body:JSON.stringify({current_password,new_password})}),
  documents: () => request<Document[]>('/documents'),
  upload: (file:File, title:string) => { const body=new FormData(); body.append('file',file); if(title) body.append('title',title); return request<Document>('/documents',{method:'POST',body}) },
  deleteDocument: (id:number) => request<void>(`/documents/${id}`,{method:'DELETE'}),
  concepts: (id:number) => request<Concept[]>(`/documents/${id}/concepts`),
  chunks: (id:number) => request<Chunk[]>(`/documents/${id}/chunks`),
  createTest: (documentId:number,count=10) => request<{id:number;mode:string;questions:Question[]}>('/tests',{method:'POST',body:JSON.stringify({mode:'practice',document_ids:[documentId],count})}),
  answer: (attemptId:number,questionId:number,response:string) => request<{correct:boolean;marks:number;answer:string;explanation:string;source_quote:string;page:number}>(`/attempts/${attemptId}/answers`,{method:'POST',body:JSON.stringify({question_id:questionId,response})}),
  submit: (attemptId:number) => request<{score:number;answered:number}>(`/attempts/${attemptId}/submit`,{method:'POST'}),
  dashboard: () => request<{accuracy:number;answers:number;weak_concepts:{id:number;name:string;score:number}[];study_next:string|null}>('/dashboard'),
  chat: (documentIds:number[],message:string) => request<{answer:string;citations:Citation[]}>('/chat',{method:'POST',body:JSON.stringify({document_ids:documentIds,message,k:4})}),
  artifacts: () => request<Artifact[]>('/artifacts'),
  generateArtifact: (payload:{title:string;topic:string;artifact_type:string;document_ids:number[];constraints:Record<string,unknown>}) => request<Artifact>('/artifacts/generate',{method:'POST',body:JSON.stringify(payload)}),
  submitArtifact: (id:number) => request<{id:number;status:string}>(`/artifacts/${id}/submit`,{method:'POST'}),
  resume: () => request<Resume>('/career/resume'),
  uploadResume: (file:File) => { const body=new FormData(); body.append('file',file); return request<Resume>('/career/resume',{method:'POST',body}) },
  confirmResume: (profile:ResumeProfile) => request<Resume>('/career/resume/profile',{method:'PATCH',body:JSON.stringify(profile)}),
  deleteResume: () => request<void>('/career/resume',{method:'DELETE'}),
  careerGoal: () => request<CareerGoal>('/career/goals/current'),
  saveCareerGoal: (payload:{target_role:string;experience_level:string;job_description:string|null;interests:string[];deadline:string|null;weekly_hours:number}) => request<CareerGoal>('/career/goals',{method:'POST',body:JSON.stringify(payload)}),
  preparationPlan: () => request<PreparationPlan>('/career/plans/current'),
  generatePreparationPlan: () => request<PreparationPlan>('/career/plans/generate',{method:'POST'}),
  updatePreparationTask: (id:number,completed:boolean) => request<PreparationTask>(`/career/tasks/${id}`,{method:'PATCH',body:JSON.stringify({completed})}),
  pdfBlob: async (id:number) => { const token=localStorage.getItem('prepmate_token'); const response=await fetch(`${BASE}/documents/${id}/file`,{headers:{Authorization:`Bearer ${token}`}}); if(!response.ok) throw new Error('Could not load PDF'); return response.blob() },
  openPdf: async (id:number,page=1) => { const blob=await api.pdfBlob(id); const url=URL.createObjectURL(blob); window.open(`${url}#page=${page}`,'_blank');setTimeout(()=>URL.revokeObjectURL(url),60000) },
  downloadPdf: async (doc:Document) => { const blob=await api.pdfBlob(doc.id);const url=URL.createObjectURL(blob);const link=window.document.createElement('a');link.href=url;link.download=doc.filename;window.document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url) },
}
