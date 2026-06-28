import { useState } from 'react';
import { Link } from 'react-router';
import {
  Card,
  CardContent,
  Button,
  Input,
  Label,
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
  Alert,
} from '@databricks/appkit-ui/react';
import { Plus, Trash2, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Page, PageHeader, ErrorText } from '../components/kit';
import { api, type TeamMember } from '../api';
import { TRACKS } from '../content';

type MemberRow = { name: string; email: string };

export default function RegisterPage() {
  const [teamName, setTeamName] = useState('');
  const [track, setTrack] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [members, setMembers] = useState<MemberRow[]>([{ name: '', email: '' }]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function updateMember(i: number, patch: Partial<MemberRow>) {
    setMembers((prev) => prev.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  }
  function addMember() {
    setMembers((prev) => [...prev, { name: '', email: '' }]);
  }
  function removeMember(i: number) {
    setMembers((prev) => prev.filter((_, idx) => idx !== i));
  }

  const cleanedMembers = members
    .map((m) => ({ name: m.name.trim(), email: m.email.trim() }))
    .filter((m) => m.name.length > 0);

  const canSubmit =
    !pending && teamName.trim().length > 0 && track.length > 0 && cleanedMembers.length > 0;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setPending(true);
    setError(null);
    try {
      const payload: {
        team_name: string;
        track: string;
        contact_email?: string;
        members: TeamMember[];
      } = {
        team_name: teamName.trim(),
        track,
        members: cleanedMembers.map((m) => ({
          name: m.name,
          ...(m.email ? { email: m.email } : {}),
        })),
      };
      if (contactEmail.trim()) payload.contact_email = contactEmail.trim();
      await api.createTeam(payload);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Participate"
        title="Register a team"
        subtitle="Pick a track and add your crew. You can refine your submission later from the Teams page."
      />

      <div className="mx-auto w-full max-w-xl">
        <Card>
          <CardContent className="pt-6">
            {success ? (
              <div className="flex flex-col gap-4">
                <Alert>
                  <CheckCircle2 className="h-4 w-4" />
                  <div>
                    <div className="font-semibold text-foreground">
                      {teamName.trim()} is registered.
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Your team is in. Head to the Teams page to see it and start a submission.
                    </p>
                  </div>
                </Alert>
                <Button asChild>
                  <Link to="/teams">
                    View teams <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="flex flex-col gap-5">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="team_name">Team name</Label>
                  <Input
                    id="team_name"
                    value={teamName}
                    onChange={(e) => setTeamName(e.target.value)}
                    placeholder="The Variance Hunters"
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="track">Track</Label>
                  <Select value={track} onValueChange={setTrack}>
                    <SelectTrigger id="track">
                      <SelectValue placeholder="Choose a hackathon track" />
                    </SelectTrigger>
                    <SelectContent>
                      {TRACKS.map((t) => (
                        <SelectItem key={t.key} value={t.key}>
                          {t.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="contact_email">
                    Contact email <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="contact_email"
                    type="email"
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    placeholder="captain@akzonobel.com"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Label>Members</Label>
                    <Button type="button" variant="ghost" size="sm" onClick={addMember}>
                      <Plus className="mr-1.5 h-3.5 w-3.5" /> Add member
                    </Button>
                  </div>
                  <div className="flex flex-col gap-3">
                    {members.map((m, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Input
                          value={m.name}
                          onChange={(e) => updateMember(i, { name: e.target.value })}
                          placeholder="Name"
                          aria-label={`Member ${i + 1} name`}
                        />
                        <Input
                          type="email"
                          value={m.email}
                          onChange={(e) => updateMember(i, { email: e.target.value })}
                          placeholder="Email (optional)"
                          aria-label={`Member ${i + 1} email`}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeMember(i)}
                          disabled={members.length === 1}
                          aria-label={`Remove member ${i + 1}`}
                          className="shrink-0 text-muted-foreground"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    At least one member with a name is required.
                  </p>
                </div>

                {error && <ErrorText>{error}</ErrorText>}

                <Button type="submit" disabled={!canSubmit}>
                  {pending ? 'Registering…' : 'Register team'}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </Page>
  );
}
