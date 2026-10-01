export type LegalDocumentId = 'legal' | 'privacy' | 'terms'

export type LegalDocumentLink = {
  id: LegalDocumentId
  path: string
  label: string
}

export type GoupixDexLegalDocumentProps = {
  documentId: LegalDocumentId
  title: string
  intro: string
}
