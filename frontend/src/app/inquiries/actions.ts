"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  createInquiry,
  updateInquiryStatus,
} from "@/lib/inquiries/repository";
import type { Inquiry } from "@/lib/inquiries/types";
import {
  parseCreateInquiryInput,
  parseInquiryStatusUpdate,
} from "@/lib/inquiries/validation";
import type {
  CreateInquiryFormState,
  UpdateInquiryStatusFormState,
} from "@/lib/inquiries/validation";

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

/**
 * 問い合わせのステータス変更。id・status とも FormData で受け取り改ざんされ得るため、
 * サーバー側で検証し、存在確認は repository の戻り値で行う。
 */
export async function updateInquiryStatusAction(
  _prevState: UpdateInquiryStatusFormState,
  formData: FormData,
): Promise<UpdateInquiryStatusFormState> {
  const result = parseInquiryStatusUpdate(formData);
  if (!result.success) {
    return { error: result.error };
  }
  const { id, status } = result;

  let updated: Inquiry | null;
  try {
    updated = await updateInquiryStatus(id, status);
  } catch {
    return { error: "更新に失敗しました。時間をおいて再度お試しください。" };
  }

  if (!updated) {
    return { error: "問い合わせが見つかりません" };
  }

  revalidatePath(`/inquiries/${id}`);
  revalidatePath("/inquiries");
  return { message: "ステータスを更新しました" };
}
