"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createInquiry } from "@/lib/inquiries/repository";
import { parseCreateInquiryInput } from "@/lib/inquiries/validation";
import type { CreateInquiryFormState } from "@/lib/inquiries/validation";

/**
 * 新規問い合わせ登録。直接 POST でも呼び出せるため、必ずサーバー側で検証する。
 * 成功時は作成した問い合わせの詳細画面へ redirect する。
 */
export async function createInquiryAction(
  _prevState: CreateInquiryFormState,
  formData: FormData,
): Promise<CreateInquiryFormState> {
  const result = parseCreateInquiryInput(formData);
  if (!result.success) {
    return { errors: result.errors, values: result.values };
  }

  let id: string;
  try {
    const created = await createInquiry(result.data);
    id = created.id;
  } catch {
    return {
      formError: "登録に失敗しました。時間をおいて再度お試しください。",
      values: result.data,
    };
  }

  revalidatePath("/inquiries");
  // redirect は例外で遷移するため try/catch の外で呼ぶ
  redirect(`/inquiries/${id}`);
}
