import { useState } from "react";
import { OnboardingLayout } from "./OnboardingLayout";
import { useOnboardingState } from "./useOnboardingState";
import { PracticeDetailsStep } from "./steps/PracticeDetailsStep";
import { FirstDoctorStep } from "./steps/FirstDoctorStep";
import { ChannelsStep } from "./steps/ChannelsStep";
import { CompleteStep } from "./steps/CompleteStep";
import type { OnboardingStepId } from "./types";

const STEP_IDS: OnboardingStepId[] = ["practice", "doctor", "channels"];

// 3 skippable steps + a completion screen. Resumable via
// useOnboardingState — a reload mid-wizard doesn't lose progress, and
// there's no dead end: every step can be skipped, and Overview's
// SetupChecklist (dashboard/overview/SetupChecklist.tsx) picks up anything
// left unfinished for someone who skips straight through.
export function SetupWizardPage() {
  const { state, completeStep } = useOnboardingState();
  const [index, setIndex] = useState(() => {
    const firstUnfinished = STEP_IDS.findIndex((s) => !state.completedSteps.includes(s));
    return firstUnfinished === -1 ? STEP_IDS.length : firstUnfinished;
  });

  function advance(id: OnboardingStepId) {
    completeStep(id);
    setIndex((i) => i + 1);
  }

  const skip = () => setIndex((i) => i + 1);

  return (
    <OnboardingLayout step={{ current: 3, total: 3 }}>
      {index === 0 && <PracticeDetailsStep onNext={() => advance("practice")} onSkip={skip} />}
      {index === 1 && <FirstDoctorStep onNext={() => advance("doctor")} onSkip={skip} />}
      {index === 2 && <ChannelsStep onNext={() => advance("channels")} onSkip={skip} />}
      {index >= 3 && <CompleteStep />}
    </OnboardingLayout>);

}
