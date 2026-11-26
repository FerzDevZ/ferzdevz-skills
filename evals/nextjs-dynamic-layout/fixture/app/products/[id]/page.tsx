import { getProduct } from '@/lib/catalog'

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const product = await getProduct(id)
  return <main><h1>{product.name}</h1></main>
}
